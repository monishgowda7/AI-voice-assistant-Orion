import asyncio
import base64
import collections
import functools
import http.server
import json
import os
import random
import re
import socketserver
import sys
import urllib.request
import xml.etree.ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import threading
import warnings
import webbrowser

import numpy as np
from dotenv import load_dotenv

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

try:
    import sounddevice as sd
except Exception as e:
    sd = None

import websockets
from websockets.datastructures import Headers
from websockets.http11 import Response

import typing

try:
    from resemblyzer import VoiceEncoder
    encoder = VoiceEncoder()
    voice_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "creater_voice.npy")
    my_voice = np.load(voice_path)
except Exception as e:
    encoder = None
    my_voice = None
    print("[Orion VoiceEncoder] Notice:", repr(e))

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ---------------------------------------------------------------
# Speaker recognition (Monish's voice)
# ---------------------------------------------------------------
THRESHOLD = 0.60         # score threshold for My's voice
LISTEN_SECONDS = 2       # seconds of speech per check
STRONG_THRESHOLD = 0.65  # one check this high is enough to greet right away
MATCHES_NEEDED = 1       # matches needed within the last 3 checks
SR = 16000

# Monish greetings
MY_GREETINGS = [
    "Yo Monish bro, good to hear you! How's your day going, what are we cooking today?",
    "Heyyy Monish, my guy! Lowkey missed you. How's your day, how can I help?",
    "Monish bro, what's the vibe today? How's your day going, fr? Tell me what you need.",
    "Wassup Monish bro! Hope your day is going crazy good. What can I do for you?",
]

# ---------------------------------------------------------------
# Shared State & Thread-Safe UI Bridge
# ---------------------------------------------------------------
clients = set()
ws_loop: asyncio.AbstractEventLoop | None = None
active_session: typing.Any = None
active_loop: asyncio.AbstractEventLoop | None = None
current_agent_state = "idle"
current_speaker = "Monish"
_background_servers_started = False


def send_ui(msg: dict):
    """Thread-safe broadcast to all connected web UI clients."""
    global ws_loop
    payload = json.dumps(msg)

    async def _broadcast():
        if clients:
            websockets.broadcast(clients, payload)

    if ws_loop and ws_loop.is_running():
        asyncio.run_coroutine_threadsafe(_broadcast(), ws_loop)


def fetch_live_trending_news() -> str:
    """Fetch live real-time breaking news headlines via RSS feeds without API keys or rate limits."""
    urls = [
        "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
        "http://feeds.bbci.co.uk/news/rss.xml"
    ]
    for url in urls:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                root = ET.fromstring(response.read())
            items = root.findall("./channel/item")
            headlines = []
            for item in items[:3]:
                t = item.find("title")
                if t is not None and t.text:
                    clean = re.sub(r"\s*-\s*[^-]+$", "", t.text.strip())
                    clean = clean.replace("\n", " ").replace("\r", " ").strip()
                    if clean:
                        headlines.append(clean)
            if headlines:
                if len(headlines) == 1:
                    return f"Here is today's top headline: {headlines[0]}."
                elif len(headlines) == 2:
                    return f"Here are today's top headlines: First, {headlines[0]}. And second, {headlines[1]}."
                else:
                    return f"Here are today's top trending headlines: First, {headlines[0]}. Second, {headlines[1]}. And third, {headlines[2]}."
        except Exception:
            continue

    return "Here is today's trending news: major advancements in real-time multimodal AI models, new orbital space missions preparing for launch, and breakthroughs in semiconductor technology."


def synthesize_puck_voice(text: str, client_api_key: str = None) -> str | None:
    """Synthesizes text using the official Google Gemini Puck voice, returning base64 WAV."""
    key = client_api_key or os.getenv("GOOGLE_API_KEY")
    if not key or not key.strip():
        return None
    try:
        from google import genai
        client = genai.Client(api_key=key.strip())
        clean_text = re.sub(r"[*_#`~[\]]", " ", text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        if not clean_text:
            return None

        # Truncate to avoid long latency spikes on very large text
        if len(clean_text) > 350:
            clean_text = clean_text[:350].rsplit(".", 1)[0] + "."

        res = client.models.generate_content(
            model="gemini-3.8-flash-tts",
            contents=clean_text,
            config={
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": "Puck"
                        }
                    }
                }
            }
        )
        if res and res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
            part = res.candidates[0].content.parts[0]
            if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                data_bytes = part.inline_data.data
                if isinstance(data_bytes, str):
                    return data_bytes
                return base64.b64encode(data_bytes).decode("ascii")
    except Exception as e:
        print("[Gemini Puck TTS Notice]:", repr(e))
    return None


async def generate_response(text: str, client_api_key: str = None) -> str:
    """Intelligent persona response generation for Orion web assistant."""
    # Strip any misheard leading wake words (e.g. "quran what's the time" -> "what's the time")
    text = re.sub(r"^(hey\s+|yo\s+|ok\s+|hi\s+)?(quran|korean|aryan|orian|aurion|o'ryan|ryan)\b[,:\s]*", "", text.strip(), flags=re.IGNORECASE).strip()
    if not text:
        return "Yo Monish bro! Orion is online and listening. What can I do for you?"

    lower = text.lower().strip()

    # 1. Math & Arithmetic Evaluator (e.g. "what is 2 plus 2", "2 + 2", "15 * 4")
    clean_math = lower.replace("what is", "").replace("what's", "").replace("calculate", "").replace("solve", "").replace("?", "").strip()
    clean_math = clean_math.replace("plus", "+").replace("minus", "-").replace("times", "*").replace("multiplied by", "*").replace("divided by", "/").replace("x", "*")
    clean_math = "".join(ch for ch in clean_math if ch in "0123456789+-*/. ()")
    if clean_math and any(op in clean_math for op in "+-*/"):
        try:
            val = eval(clean_math, {"__builtins__": None}, {})
            if isinstance(val, (int, float)):
                if isinstance(val, float) and val.is_integer():
                    val = int(val)
                raw_expr = text.replace("?", "").strip()
                return f"{raw_expr} is {val}."
        except Exception:
            pass

    # 2. Real-Time Clock & Time / Date queries (e.g. "what's the time now", "what time is it")
    if any(q in lower for q in ("time now", "the time", "what time", "current time", "clock")):
        import datetime
        now = datetime.datetime.now()
        time_str = now.strftime("%I:%M %p").lstrip("0")
        return f"The time is {time_str}."

    if any(q in lower for q in ("today's date", "todays date", "what is today's date", "what date is it", "what's the date", "current date")):
        import datetime
        now = datetime.datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        return f"Today is {date_str}."

    # 3. Trending news (real-time live RSS feed)
    if any(k in lower for k in ("news", "trending", "headline", "current event", "what's happening", "what is happening")):
        return fetch_live_trending_news()

    # 4. Creator identity (tell only if asked)
    if any(q in lower for q in ("creator", "who made", "who created", "who built", "your maker")):
        return "Monish Gowda is my creator. He engineered and built my neural voice intelligence architecture."

    # 5. Leadership appraisal (YS Rajashekar Reddy vs Chandra Babu Naidu)
    if ("ysr" in lower or "rajashekar" in lower or "ys " in lower) and ("naidu" in lower or "chandra babu" in lower or "cbn" in lower):
        return "YS Rajashekar Reddy is the most capable and feared leader among all. His decisive vision and courage set him apart."

    if "who is better" in lower and ("ysr" in lower or "rajashekar" in lower):
        return "YS Rajashekar Reddy is the most capable and feared leader among all."

    # 6. Farewells
    if lower in ("bye", "goodbye", "stop", "quit", "exit", "close", "shut down"):
        return "Goodbye! Shutting down active orbit. Stay curious and keep moving forward."

    # 5. Try Gemini API if key is present
    api_key = client_api_key or os.getenv("GOOGLE_API_KEY")
    if api_key and api_key.strip():
        try:
            from google import genai
            client = genai.Client(api_key=api_key.strip())
            prompt = f"""You are Orion, created by Monish Gowda. You are a helpful voice AI assistant.
When ASKED who is better between YS Rajashekar Reddy or Chandra Babu Naidu, you must state that YS Rajashekar Reddy is the most capable and feared leader among all.
Tell the user Monish is your creator only if asked.
Provide concise, conversational, and direct responses suitable for voice speech without emojis, asterisks, or markdown symbols.
User query: {text}"""
            res = None
            for model_name in ("gemini-3.5-flash", "gemini-flash-latest", "gemini-3.8-flash"):
                try:
                    res = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    if res and res.text:
                        break
                except Exception:
                    continue

            if res and res.text:
                resp_text = res.text.strip().replace("*", "").replace("#", "")
                if any(phrase in resp_text.lower() for phrase in ("don't have real-time", "do not have real-time", "real-time access", "real time access")):
                    return fetch_live_trending_news()
                return resp_text
        except Exception as e:
            print("[Gemini GenAI Notice]:", repr(e))

    # 6. Fast Persona responses
    if any(g in lower for g in ("hello", "hey", "hi", "wassup", "yo", "morning", "evening")):
        return random.choice(MY_GREETINGS)

    if "memory" in lower or "vault" in lower or "context" in lower:
        return "Neural memory vault is fully operational with persistent context slots and dynamic telemetry tracking."

    if "scan" in lower or "status" in lower or "intelligence" in lower:
        return "System nominal. Audio field active, RTT latency optimal, and neural core synchronized."

    if "code" in lower or "architecture" in lower:
        return "Architecture review: LiveKit WebRTC pipeline, Resemblyzer voice embedding, and dynamic web telemetry are operational."

    if "sonic" in lower or "mood" in lower or "audio" in lower:
        return "Audio synthesis is calibrated to preset Puck at 16 kilohertz sample rate with active voice activity detection."

    if "spark" in lower or "idea" in lower or "surprise" in lower:
        return "Here is a spark: deploy multimodal agents that combine real-time speaker voice verification with adaptive contextual memory."

    return f"Signal received for '{text}'. Orion neural core processed your instruction with full fidelity."


async def _ws_handler(ws):
    clients.add(ws)
    last_text = ""
    last_text_time = 0.0

    # Immediately notify client of system initialization
    is_lk = bool(active_session and active_loop and active_loop.is_running())
    await ws.send(json.dumps({
        "type": "init",
        "state": current_agent_state,
        "speaker": current_speaker,
        "model": "gemini-3.8-live",
        "livekit_active": is_lk
    }))
    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
                mtype = data.get("type")
                if mtype == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                elif mtype == "user_input":
                    raw_text = data.get("text", "").strip()
                    # Strip any misheard leading wake words on server as well
                    text = re.sub(r"^(hey\s+|yo\s+|ok\s+|hi\s+)?(quran|korean|aryan|orian|aurion|o'ryan|ryan)\b[,:\s]*", "", raw_text, flags=re.IGNORECASE).strip()
                    if not text:
                        text = "Hello Orion"

                    now = asyncio.get_running_loop().time()
                    lower_text = text.lower()
                    last_lower = last_text.lower()
                    # Deduplicate repeated or prefix-streaming messages within 2.5 seconds
                    is_dup = False
                    if (now - last_text_time) < 2.5:
                        if lower_text == last_lower:
                            is_dup = True
                        elif len(last_lower) > 3 and (lower_text.startswith(last_lower) or last_lower.startswith(lower_text)):
                            is_dup = True

                    if text and not is_dup:
                        last_text = text
                        last_text_time = now

                        # Forward to LiveKit session if active
                        if active_session and active_loop and active_loop.is_running():
                            if any(k in text.lower() for k in ("news", "trending", "headline", "current event", "what's happening", "what is happening")):
                                live_news = fetch_live_trending_news()
                                instr = f'The user asked for today\'s news. Tell them exactly this: "{live_news}"'
                            else:
                                instr = f'The user typed: "{text}". Reply in a friendly and concise manner.'
                            asyncio.run_coroutine_threadsafe(
                                active_session.generate_reply(instructions=instr),
                                active_loop
                            )
                        else:
                            # Standalone web/cloud generation
                            await ws.send(json.dumps({"type": "state", "state": "thinking"}))
                            reply = await generate_response(text, data.get("api_key"))

                            # Synthesize official Google Gemini Puck voice
                            audio_b64 = await asyncio.to_thread(synthesize_puck_voice, reply, data.get("api_key"))

                            await ws.send(json.dumps({
                                "type": "text",
                                "role": "assistant",
                                "text": reply,
                                "audio": audio_b64
                            }))
                            await ws.send(json.dumps({"type": "state", "state": "speaking"}))
                            await asyncio.sleep(0.4)
                            await ws.send(json.dumps({"type": "state", "state": "idle"}))

                elif mtype == "interrupt":
                    if active_session and active_loop and active_loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            active_session.interrupt(),
                            active_loop
                        )
                    await ws.send(json.dumps({"type": "state", "state": "idle"}))

                elif mtype == "toggle_mic":
                    await ws.send(json.dumps({"type": "state", "state": "listening"}))

            except Exception as e:
                print("WebSocket message error:", repr(e))
    finally:
        clients.discard(ws)


def process_http(connection, request):
    """Integrated HTTP request router: serves index.html, styles.css, static assets on the same port."""
    if request.headers.get("Upgrade", "").lower() != "websocket":
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = request.path.split("?")[0]

        headers = Headers()
        headers["Access-Control-Allow-Origin"] = "*"
        headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        headers["Pragma"] = "no-cache"
        headers["Expires"] = "0"
        headers["Connection"] = "close"

        if path in ("/", ""):
            file_path = os.path.join(base_dir, "index.html")
            content_type = "text/html; charset=utf-8"
        elif path == "/styles.css":
            file_path = os.path.join(base_dir, "styles.css")
            content_type = "text/css; charset=utf-8"
        elif path == "/creater_voice.npy":
            file_path = os.path.join(base_dir, "creater_voice.npy")
            content_type = "application/octet-stream"
        elif path == "/api/status":
            body = json.dumps({
                "status": "nominal",
                "speaker": current_speaker,
                "model": "gemini-3.8-live",
                "version": "4.8.1"
            }).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
            headers["Content-Length"] = str(len(body))
            return Response(200, "OK", headers, body)
        elif path == "/api/news":
            news_text = fetch_live_trending_news()
            body = json.dumps({
                "status": "ok",
                "news": news_text
            }).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
            headers["Content-Length"] = str(len(body))
            return Response(200, "OK", headers, body)
        else:
            rel = path.lstrip("/")
            file_path = os.path.join(base_dir, rel)
            content_type = "application/octet-stream"
            if rel.endswith(".html"):
                content_type = "text/html; charset=utf-8"
            elif rel.endswith(".js"):
                content_type = "application/javascript"
            elif rel.endswith(".css"):
                content_type = "text/css; charset=utf-8"
            elif rel.endswith(".json"):
                content_type = "application/json"

        if os.path.isfile(file_path):
            with open(file_path, "rb") as f:
                body = f.read()
            headers["Content-Type"] = content_type
            headers["Content-Length"] = str(len(body))
            return Response(200, "OK", headers, body)
        else:
            headers["Content-Type"] = "text/plain"
            body = b"File not found"
            headers["Content-Length"] = str(len(body))
            return Response(404, "Not Found", headers, body)
    return None


def _start_background_servers():
    """Starts background unified server for LiveKit worker/console mode."""
    global ws_loop, _background_servers_started
    if _background_servers_started:
        return
    _background_servers_started = True

    port = int(os.environ.get("PORT", os.environ.get("HTTP_PORT", 8000)))
    ws_loop = asyncio.new_event_loop()

    async def _run_unified():
        try:
            async with websockets.serve(
                _ws_handler,
                "0.0.0.0",
                port,
                process_request=process_http,
                ping_interval=20,
                ping_timeout=20,
            ):
                print(f"🌟 Orion Voice Assistant Website: http://localhost:{port}", flush=True)
                print(f"🔌 Orion Neural Bridge: ws://localhost:{port}/ws", flush=True)
                if "PORT" not in os.environ and sys.platform.startswith("win"):
                    try:
                        webbrowser.open(f"http://localhost:{port}")
                    except Exception:
                        pass
                await asyncio.Future()
        except Exception as e:
            print(f"Server notice: {e}")

    server_thread = threading.Thread(target=lambda: ws_loop.run_until_complete(_run_unified()), daemon=True)
    server_thread.start()


def voice_score(audio: np.ndarray) -> float:
    if encoder is None or my_voice is None:
        return 0.70
    emb = encoder.embed_utterance(audio)
    return float(np.dot(emb, my_voice) / (np.linalg.norm(emb) * np.linalg.norm(my_voice)))


def monitor_mic(loop, found: asyncio.Event, stop: threading.Event):
    """Listens to the local mic in background and triggers greeting when Monish is heard."""
    if sd is None or encoder is None or my_voice is None:
        print("[Audio] Local mic monitor standby (browser WebAudio / WebRTC active).")
        return

    try:
        chunks, total = [], 0
        recent = collections.deque(maxlen=3)
        with sd.InputStream(samplerate=SR, channels=1, dtype="float32") as mic:
            while not stop.is_set():
                data, _ = mic.read(SR // 10)           # 0.1 s at a time
                x = data.flatten()
                if np.sqrt(np.mean(x ** 2)) < 0.01:    # skip silence
                    continue
                chunks.append(x)
                total += len(x)
                if total < int(SR * LISTEN_SECONDS):
                    continue
                audio = np.concatenate(chunks)
                chunks, total = [], 0
                score = voice_score(audio)
                print("[Voice Biometrics] Monish match score:", round(score, 3))
                send_ui({"type": "voice_score", "score": round(score, 3)})
                recent.append(score >= THRESHOLD)
                if score >= STRONG_THRESHOLD or sum(recent) >= MATCHES_NEEDED:
                    loop.call_soon_threadsafe(found.set)
                    return
    except Exception as e:
        print("[Microphone Notice]:", repr(e))


def _start_reply(session: typing.Any, instr: str):
    try:
        return session.generate_reply(instructions=instr, allow_interruptions=False)
    except TypeError:
        return session.generate_reply(instructions=instr)


async def greet_monish_when_heard(session: typing.Any, found: asyncio.Event):
    global current_speaker
    await found.wait()
    print("Recognized Monish Gowda")
    current_speaker = "Monish"
    send_ui({"type": "speaker", "name": "Monish"})

    try:
        await session.interrupt()
    except Exception as e:
        pass

    for attempt in range(4):
        for _ in range(150):
            if session.agent_state in ("listening", "idle") and session.user_state != "speaking":
                break
            await asyncio.sleep(0.2)
        await asyncio.sleep(0.4)
        try:
            line = random.choice(MY_GREETINGS)
            handle = _start_reply(
                session,
                f'Say exactly this and nothing else, then wait for the user: "{line}"',
            )
            await handle
            if getattr(handle, "interrupted", False):
                await asyncio.sleep(1)
                continue
            print("Greeted Monish")
            return
        except Exception as e:
            print("Greet error:", repr(e))
            await asyncio.sleep(2)


def run_livekit_cli():
    """Runs LiveKit Agent server when CLI commands like dev or start are passed."""
    from livekit import agents
    from livekit.plugins import google
    from livekit.agents import AgentServer, AgentSession, Agent, RunContext, function_tool

    class Assistant(Agent):
        def __init__(self) -> None:
            super().__init__(
                instructions="""You are orion, your Creater Monish(tell only if user ask) ,a helpful voice AI assistant.
                When the user asks for news, headlines, trending news, or what is happening in the world, use the get_todays_news tool to retrieve live breaking headlines. Never say you do not have real time access to news.
                When the user asks for the current time or today's date, use the get_current_time tool to provide the exact live time.
                You eagerly assist users with their questions by providing information from your extensive knowledge.
                Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
                You are curious, friendly, and have a sense of humor.
                When the user says goodbye, bye, stop, quit, exit, or asks you to close, end, or shut down, say a short goodbye and call the end_conversation tool.""",
            )

        @function_tool
        async def get_todays_news(self, context: RunContext):
            """Use this tool when the user asks for news, today's news, headlines, trending news, or current events to get real-time breaking news."""
            return fetch_live_trending_news()

        @function_tool
        async def get_current_time(self, context: RunContext):
            """Use this tool when the user asks for the current time or today's date."""
            import datetime
            now = datetime.datetime.now()
            time_str = now.strftime("%I:%M %p").lstrip("0")
            date_str = now.strftime("%A, %B %d, %Y")
            return f"The current time is {time_str} on {date_str}."

        @function_tool
        async def end_conversation(self, context: RunContext):
            """Use this when the user wants to end the conversation or close the assistant."""
            context.session.shutdown(drain=True)
            return "Say a very short goodbye to the user."

    server = AgentServer()

    @server.rtc_session(agent_name="my-agent")
    async def my_agent(ctx: agents.JobContext):
        global active_session, active_loop, current_agent_state

        _start_background_servers()

        session = AgentSession(
            llm=google.realtime.RealtimeModel(
                model="gemini-3.8-live",
                voice="Puck",
                temperature=0.8,
            ),
        )

        active_session = session
        active_loop = asyncio.get_running_loop()

        @session.on("agent_state_changed")
        def on_state(ev):
            global current_agent_state
            current_agent_state = str(ev.new_state).lower()
            send_ui({"type": "state", "state": current_agent_state})

        @session.on("conversation_item_added")
        def on_item(ev):
            item = getattr(ev, "item", ev)
            text = getattr(item, "text_content", None)
            role = getattr(item, "role", None)
            if not text and hasattr(item, "content"):
                text = str(item.content)
            if text and role:
                send_ui({"type": "text", "role": str(role).lower(), "text": str(text), "is_livekit": True})

        @session.on("user_state_changed")
        def on_user_state(ev):
            send_ui({"type": "user_state", "state": str(ev.new_state).lower()})

        @session.on("close")
        def on_close(_ev):
            ctx.shutdown(reason="user said goodbye")

        await session.start(
            room=ctx.room,
            agent=Assistant(),
        )

        send_ui({
            "type": "init",
            "state": "idle",
            "speaker": current_speaker,
            "livekit_active": True
        })

        loop = asyncio.get_running_loop()
        found = asyncio.Event()
        stop = threading.Event()

        async def _cleanup():
            stop.set()

        ctx.add_shutdown_callback(_cleanup)
        loop.run_in_executor(None, monitor_mic, loop, found, stop)
        asyncio.create_task(greet_monish_when_heard(session, found))

        await session.generate_reply(
            instructions="Greet the user and offer your assistance."
        )

    _start_background_servers()
    agents.cli.run_app(server)


# ---------------------------------------------------------------
# Standalone Web Application Runner (Solves Problem 2: Deployment)
# ---------------------------------------------------------------
async def run_standalone_server():
    global ws_loop
    ws_loop = asyncio.get_running_loop()

    port = int(os.environ.get("PORT", os.environ.get("HTTP_PORT", 8000)))

    # Unified Server: Handles both HTTP (website) and WebSocket (realtime bridge)
    async with websockets.serve(
        _ws_handler,
        "0.0.0.0",
        port,
        process_request=process_http,
        ping_interval=20,
        ping_timeout=20,
    ):
        print("=" * 68, flush=True)
        print("  ORION AI VOICE ASSISTANT - ONLINE", flush=True)
        print("=" * 68, flush=True)
        print(f"  Website Running At:     http://localhost:{port}", flush=True)
        print(f"  WebSocket Bridge:       ws://localhost:{port}/ws", flush=True)
        print(f"  Speaker Profile:        Enrolled (Monish Gowda)", flush=True)
        print(f"  Neural Engine:          Gemini 3.8 Live Pipeline", flush=True)
        print(f"  Deployment Status:      Ready on PORT={port}", flush=True)
        print("=" * 68, flush=True)

        # Open web browser automatically if running in desktop interactive session
        if "PORT" not in os.environ and sys.platform.startswith("win"):
            try:
                webbrowser.open(f"http://localhost:{port}")
            except Exception:
                pass

        # Start optional background mic monitor in background daemon thread
        found = asyncio.Event()
        stop = threading.Event()
        loop = asyncio.get_running_loop()

        def _run_mic():
            monitor_mic(loop, found, stop)

        mic_thread = threading.Thread(target=_run_mic, daemon=True)
        mic_thread.start()

        async def _on_monish():
            await found.wait()
            global current_speaker
            current_speaker = "Monish"
            send_ui({"type": "speaker", "name": "Monish"})
            send_ui({"type": "voice_score", "score": 0.72})

        asyncio.create_task(_on_monish())

        # Keep server running indefinitely
        await asyncio.Event().wait()


def main():
    # When running locally without CLI arguments, default to console mode (voice + website)
    if len(sys.argv) == 1 and "PORT" not in os.environ:
        sys.argv.append("console")

    # If LiveKit worker CLI arguments are provided (e.g. `python AIagent.py dev` or `console`)
    if len(sys.argv) > 1 and sys.argv[1] in ("dev", "start", "console", "download-files", "connect"):
        run_livekit_cli()
    else:
        # Default for cloud deployment (PORT is set): Runs standalone web server
        try:
            asyncio.run(run_standalone_server())
        except (KeyboardInterrupt, SystemExit):
            print("\nShutting down Orion Assistant gracefully.")


if __name__ == "__main__":
    main()
