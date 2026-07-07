# ManifestAI - Automated Motivation & Manifestation Shorts Generator

This is a friendly fork of [AutoShorts AI](https://github.com/SaarD00/AI-Youtube-Shorts-Generator) by SaarD00. All credit for the original pipeline goes to them — I just adapted it to my own needs.

Instead of telling complex stories, this version is built for **daily motivational, manifestation, and psychological insight videos**. It takes a script JSON (from Ollama or any LLM), generates voiceover, finds matching stock footage, overlays captions, and optionally uploads straight to YouTube.

---

## What changed from the original?

- **No Gemini dependency** — accepts script JSON from anywhere (Ollama, n8n, curl, etc.)
- **Added HTTP server** — listens for POST requests, no CLI needed
- **YouTube auto-upload** — one-time OAuth setup, then it posts videos automatically
- **On-screen captions** — text overlays with word wrapping and semi-transparent background
- **No avatar/mascot injection** — stripped to keep it simple for quote-based content
- **Systemd service** — runs as a daemon on Ubuntu/CasaOS, starts on boot

---

## How it works

```
Your LLM (Ollama via n8n)
       ↓ POST request with JSON script
ManifestAI server
       ↓ edge-tts voiceover
       ↓ Pexels stock videos (2 per scene for A/B split)
       ↓ FFmpeg composes everything + captions
       ↓ Either returns the video or uploads to YouTube
```

The script format is simple:
```json
[
  {"id": 1, "text": "You are worthy of everything you desire.", "visual_1": "sunrise over mountains", "visual_2": "person meditating sunset", "mood": "uplifting"},
  {"id": 2, "text": "The universe rewards those who take action.", "visual_1": "person walking path", "visual_2": "stars night sky", "mood": "inspiring"}
]
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- FFmpeg
- Pexels API key (free)

### Install

```bash
git clone <your-repo-url>
cd ContentAutomationServerSideVideoGenerator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo apt install ffmpeg -y
mkdir -p assets/{audio_clips,video_clips,temp,final,avatar}
echo "PEXELS_API_KEY=your_key_here" > .env
```

### Run as server

```bash
python main.py server 8765
```

### Or as a systemd service (auto-start on boot)

```bash
sudo nano /etc/systemd/system/manifestai.service
```

```ini
[Unit]
Description=ManifestAI Video Generator
After=network.target

[Service]
User=polar
WorkingDirectory=/home/polar/ContentAutomationServerSideVideoGenerator
ExecStart=/home/polar/ContentAutomationServerSideVideoGenerator/venv/bin/python main.py server 8765
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable manifestai
sudo systemctl start manifestai
```

---

## YouTube Upload Setup

One-time OAuth to let the server upload to your channel:

1. Go to https://console.cloud.google.com → Create project
2. Enable **YouTube Data API v3**
3. Create OAuth client ID → **Desktop app**
4. Download `client_secret.json` and place it in `assets/`
5. Run: `python setup_youtube.py`
6. Open the URL in your browser, authorize your YouTube account
7. Paste the code back in the terminal

After that, include `"youtube": true` in your POST request and the video uploads automatically.

---

## API

### POST `/generate`

**Request:**
```json
{"script": [...], "youtube": true, "title": "Daily Motivation"}
```

**Response (with upload):**
```json
{"status": "uploaded", "video_id": "abc123", "url": "https://youtu.be/abc123"}
```

**Response (without upload):**
Returns the MP4 file directly.

---

## n8n Workflow

1. **CRON** — daily trigger
2. **LLM (Ollama)** — generate script JSON
3. **Code node** — clean and format
4. **HTTP Request** — POST to the server

---

## Credits

- **Original project:** [AutoShorts AI](https://github.com/SaarD00/AI-Youtube-Shorts-Generator) by SaarD00
- **This fork:** Repurposed for motivational content, added HTTP server, captions, and YouTube upload
- **Pexels** for free stock footage
- **edge-tts** for voice generation

---

## License

Same as original — open source, go build something cool.
