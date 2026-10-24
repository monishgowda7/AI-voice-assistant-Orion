🎙️ Orion – AI Voice Assistant

Orion is an AI-powered voice assistant designed to make human-computer interaction smarter, faster, and more natural. It aims to understand voice commands, process user requests, and provide helpful responses through an intuitive voice-based interface.

✨ Features

* 🎤 Voice Input – Interact with the assistant using voice commands.
* 🧠 AI-Powered Responses – Process user requests and generate intelligent responses.
* 🔊 Voice Output – Receive responses through speech, if text-to-speech is implemented.
* ⚡ Real-Time Interaction – Designed for convenient and efficient communication.
* 💻 User-Friendly Experience – Simplifies interaction with technology through natural language.

## Features

- Real-time voice conversation powered by LiveKit Agents and Gemini live voice
- Speaker recognition using a voice embedding (recognises the owner and greets them by name; other speakers get the normal assistant experience)
- Live news headlines tool
- Current time and date tool
- Ends the conversation by voice ("goodbye", "stop", "exit")
- Web frontend (index.html and styles.css)

## Requirements

- Python 3.10 or newer
- A LiveKit project (URL, API key, API secret)
- A Gemini API key
- A working microphone and speakers

## Setup

1. Clone the repository

bash
git clone https://github.com/monishgowda7/AI-voice-assistant-Orion.git
cd AI-voice-assistant-Orion

📂 Project Structure

<pre>
AI Voice-Assistant Orion/
├── Alagent.py          # Main agent (LiveKit worker, tools, speaker check)
├── enroll.py           # Records your voice and creates the voice embedding
├── creater_voice.npy   # Saved voice embedding of the owner
├── index.html          # Frontend UI
├── styles.css          # Frontend styling
├── testing_mike.py     # Microphone test script
├── Procfile            # Process definition for deployment
├── requirements.txt    # Python dependencies
├── .env.example        # Template for environment variables
└── README.md
</pre>

The structure above is an example. Adjust the filenames and folders to match your actual project.

🚀 Getting Started

1. Clone the Repository

git clone <YOUR_GITHUB_REPOSITORY_URL>
cd Orion

2. Create a Virtual Environment (Optional)

python -m venv venv

Activate it:

Windows

venv\Scripts\activate

macOS / Linux

source venv/bin/activate

3. Install Dependencies

pip install -r requirements.txt

4. Run the Application

python main.py

Make sure your microphone is connected and any required API keys or environment variables are configured.

🎯 Project Objectives

* Make technology accessible through voice-based interaction.
* Explore practical applications of Artificial Intelligence and Natural Language Processing.
* Reduce dependence on traditional keyboard-based input.
* Build a foundation for a more capable personal AI assistant.

## Tools Available to Orion

| Tool | What it does |
|------|--------------|
| get_todays_news | Fetches live trending news headlines |
| get_current_time | Returns the current time and date |
| end_conversation | Says goodbye and closes the session |

## Tech Stack

- Python
- LiveKit Agents
- Gemini live voice
- Voice embedding for speaker recognition
- HTML, CSS, JavaScript

## Author

Monish Gowda
⸻

Built with curiosity and AI 🚀

Orion — Your voice, your commands, your AI assistant.
