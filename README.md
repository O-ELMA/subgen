# 🎬 SUBGEN

AI-powered subtitle generation from Islamic audio/video files.

## ✨ Features

- **Speech-to-Text** 🗣️ — Automatically turns spoken words in your audio or video files into written text
- **Smart Text Cleanup** 🧹 — Fixes misspelled or misheard Arabic words and common transcription mistakes while keeping the original meaning intact
- **Perfect Timing** ⏱️ — Keeps every subtitle synced to the exact right moment in the audio, so text matches what is being said
- **Clean, Readable Layout** 📖 — Handles Arabic and English together on screen, with proper line breaks and spacing so subtitles are easy to read
- **Standard Subtitle Files** 📄 — Produces `.srt` files that work with any video player (VLC, YouTube, and more)

## 💻 Installation

First, install [Python 3.12](https://www.python.org/downloads/windows/)

*Download the "Python 3.13.12 - Feb. 3, 2026" one in the page above*

### Automatically (Linux / macOS)

```bash
./linux_install.sh
```

### Automatically (Windows)

Double click:
```cmd
windows_install.bat
```

### Manually

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -U qwen-asr
```

## 🚀 Usage

```bash
python main.py <file_or_directory> [--audio|--video]
```

## ⚙️ How It Works

1. 📦 Chunk audio into ~3 min segments
2. 🎯 Transcribe with Qwen3 ASR + forced aligner
3. ✍️ Correct transcription via LLM (Arabic script restoration, error fixing)
4. 🔗 Realign word-level timestamps to corrected text
5. 📝 Format into SRT with smart line-breaking and RTL support

## 🛠️ Requirements

- Python 3.12
- PyTorch, pydub, httpx
- Qwen3-ASR-1.7B and Qwen3-ForcedAligner-0.6B models
