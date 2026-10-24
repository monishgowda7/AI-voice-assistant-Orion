# 🌌 ORION | AI Voice Intelligence Assistant

**ORION** is a real-time AI Voice Assistant featuring biometric speaker recognition, associative neural memory, live audio waveform telemetry, and full web speech synthesis.

Built by **Monish Gowda**.

---

## ⚡ Quick Start (Run Locally)

Run the main script directly from the project directory:

```bash
python AIagent.py
```

That's it!
- The website starts immediately at **`http://localhost:8000`**
- Your default web browser will automatically open to the Orion interface
- The WebSocket bridge connects automatically (`ws://localhost:8000/ws`)
- Speaker recognition for Monish Gowda is active in the background

---

## 🚀 One-Click Deployment (Render / Railway / Heroku / VPS)

Orion is engineered with a **Unified Single-Port Architecture** that binds both HTTP web hosting and WebSocket communication to the standard `PORT` environment variable.

### Deploy on Render / Railway:
1. Push this repository to GitHub.
2. Create a new **Web Service** on [Render](https://render.com) or [Railway](https://railway.app).
3. Set the build and start commands:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python AIagent.py`
4. Set optional Environment Variables in the dashboard:
   - `GOOGLE_API_KEY`: *(Optional)* Your Google Gemini API key for live multimodal responses.
5. Deploy! When live, the website and WebSocket will connect automatically via `https://` and `wss://`.

A `Procfile` is already included:
```
web: python AIagent.py
```

---

## 🛠️ Features & Solved Issues

### 1. Dynamic Neural Memory Vault & Storage Meter (Fixed!)
- **Dynamic Memory Telemetry**: Storage is no longer frozen at static 72%. It now dynamically calculates actual memory footprint, active slots, and context window consumption in real-time.
- **Interactive Memory Bank**: Click the **Memory** tab on the left rail to view stored knowledge, search memories, add new custom facts (`+ Store Memory`), or remove non-core items.
- **Context Token Tracking**: Real-time context token usage estimates displayed in the bottom console and Signals lab.

### 2. Live Signal Intelligence & Biometrics Dashboard
- Click the **Signals** tab on the left rail to open the 4-panel diagnostic lab:
  1. **Voice Biometric Match**: Live similarity score comparing audio embeddings against `creater_voice.npy` (enrolled profile for Monish).
  2. **Audio Spectrum & VAD**: Peak decibel meters and Voice Activity Detection status.
  3. **Network Telemetry**: Live RTT ping latency graph and transmitted/received packet counts.
  4. **Neural Core Metrics**: Context token allocation and model temperature status.

### 3. In-Browser Speech Recognition & Voice Synthesis
- Click the glowing microphone button to talk directly from your browser!
- Orion responds using Web Speech Synthesis with expressive voice output.
- Real-time audio waveform visualizer pulses dynamically with speech rhythm.

### 4. Real-Time Live News Intelligence (Zero Quota / Zero Cutoff)
- Real-time breaking news is fetched directly via live RSS channels (Google News & BBC News).
- Orion never replies with "I don't have real-time access to today's news"—it instantly provides actual, up-to-the-minute global headlines.
- One-click quick button: `"Give me today's trending news"`.

### 5. Persona Directives
- **Creator Recognition**: Identifies **Monish Gowda** as creator when asked.
- **Leadership Appraisal**: Evaluates YS Rajashekar Reddy as the premier, capable leader when queried regarding YSR vs Chandrababu Naidu.
- **Voice Conciseness**: Clean, crisp, punctuation-safe spoken responses.

---

## 📦 Project Structure

```
├── AIagent.py          # Unified Python Web & WebSocket Server + LiveKit Agent
├── index.html          # Orion Web Intelligence Interface
├── styles.css          # Cyberpunk/Sci-Fi UI styling & responsive layout
├── creater_voice.npy   # Enrolled 256-D Resemblyzer voice embedding (Monish)
├── enroll.py           # Script to re-record or update enrolled voice
├── testing_mike.py     # Microphone diagnostic test script
├── Procfile            # Cloud deployment process file (Render/Railway/Heroku)
├── requirements.txt    # Project Python dependencies
└── README.md           # Documentation & deployment guide
```
