# 🎬 SUBGEN

AI-powered subtitle generation from audio/video files, with a focus on Islamic content containing interspersed Arabic.

## ✨ Features

- **Speech-to-Text** 🗣️ — Automatically turns spoken words in your audio or video files into written text
- **Smart Text Cleanup** 🧹 — Fixes misspelled or misheard Arabic words and common transcription mistakes while keeping the original meaning intact
- **Perfect Timing** ⏱️ — Keeps every subtitle synced to the exact right moment in the audio, so text matches what is being said
- **Clean, Readable Layout** 📖 — Handles Arabic and English together on screen, with proper line breaks and spacing so subtitles are easy to read
- **Standard Subtitle Files** 📄 — Produces `.srt` files that work with any video player (VLC, YouTube, and more)
- **Modern GUI** 🖥️ — Drag-and-drop interface with progress tracking, file filtering, and desktop notifications
- **Batch Translation** 🌐 — Standalone tool to translate SRT files to Arabic, Dutch, Spanish, or French

## 💻 Installation


### Windows

1. Install [Python 3.12](https://www.python.org/downloads/windows/)

2. Install [FFMPEG](https://www.youtube.com/watch?v=K7znsMo_48I)

3. Double-click **`start.bat`** to start using the application

### Linux / macOS

- Install Python and FFMPEG, then run:

```bash
./linux_install.sh
```

### Manually

```bash
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate.bat
pip install -r requirements.txt
pip install -U qwen-asr --torch-backend=cpu
```

Create a `.env` file with your NanoGPT API key:
```
NANO_GPT_KEY=your_api_key_here
```

## 🚀 Usage

### GUI Mode (Default)

#### Windows

Simply double-click `start.bat`

#### Linux / macOS

```bash
python main.py
```

Features:
- **Folder Mode** — batch process all audio/video files in a directory
- **Files Mode** — select individual files
- Drag-and-drop support
- Filter by audio, video, or both
- Real-time progress bars and time estimates
- Color-coded log console
- Stop/pause functionality
- Desktop notifications on completion

### CLI Mode

```bash
python main.py --cli <path> [--audio|--video]
```

Examples:
```bash
# Single file
python main.py --cli lecture.mp4

# Directory (all files)
python main.py --cli ./lectures/

# Directory (audio only)
python main.py --cli ./lectures/ --audio

# Directory (video only)
python main.py --cli ./lectures/ --video
```

Output `.srt` files are saved in the same directory as the source. Raw transcription data is saved to `output/{basename}.json`.

### Translation Tool

Translate existing `.srt` files to another language:

```bash
python translate.py <path> --lang <ar|nl|es|fr>
```

Examples:
```bash
# Single file
python translate.py lecture.srt --lang ar

# Directory
python translate.py ./subtitles/ --lang fr

# Custom output path
python translate.py lecture.srt --lang es --output lecture_spanish.srt
```

Supported languages: `ar` (Arabic), `nl` (Dutch), `es` (Spanish), `fr` (French)

## ⚙️ How It Works

1. **📦 Audio Chunking** — Splits audio into ~3 minute segments at silence points using `pydub`
2. **🎯 Transcription** — Qwen3-ASR-1.7B transcribes each chunk with word-level timestamps
3. **🤖 Text Correction** — NanoGPT API (kimi-k2.5) corrects ASR errors and restores Arabic script
4. **🔗 Realignment** — Qwen3-ForcedAligner-0.6B realigns timestamps to the corrected text
5. **📝 Subtitle Formatting** — Converts to SRT with smart line-breaking, RTL support, and orphan-word prevention

## 📁 Supported Formats

| Audio | Video |
|-------|-------|
| MP3, WAV, FLAC, AAC, OGG, Opus | MP4, MKV, AVI, MOV, WMV, FLV |
| M4A, WMA, AIFF, ALAC, WV, TTA | WebM, M4V, MPEG, MPG, 3GP, TS |

## 🛠️ Requirements

- Python 3.12+
- PyTorch, pydub, httpx
- customtkinter + tkinterdnd2 (for GUI)
- python-dotenv
- Qwen3-ASR-1.7B and Qwen3-ForcedAligner-0.6B models (auto-downloaded)
- NanoGPT API key (for text correction and translation)

## 📂 Project Structure

| File | Purpose |
|------|---------|
| `main.py` | Entry point — launches GUI or CLI |
| `cli.py` | Command-line batch processing |
| `gui.py` | CustomTkinter GUI application |
| `ai_engine.py` | Core transcription pipeline |
| `subtitles_engine.py` | SRT formatting and timing logic |
| `translate.py` | Standalone SRT translation tool |
| `config.py` | Constants, prompts, supported formats |
| `utils.py` | Utility functions (placeholder) |

## 📄 License

MIT
