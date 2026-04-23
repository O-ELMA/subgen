#!/usr/bin/env bash
set -e

if [ ! -f .env ]; then
  echo "Paste your NanoGPT API key (leave empty to skip):"
  read -r USER_KEY

  if [ -n "$USER_KEY" ]; then
    echo "NANO_GPT_KEY=$USER_KEY" > .env
  else
    echo "NANO_GPT_KEY=" > .env
  fi
fi

PYTHON_CMD=""
for cmd in python3.12 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PYTHON_CMD=$cmd
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Error: Python is not installed. Please install Python 3.12 or higher."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo "🐍 Found Python $PYTHON_VERSION (using $PYTHON_CMD)"

echo "📦 Creating virtual environment (.venv) ..."
$PYTHON_CMD -m venv .venv

source .venv/bin/activate

if command -v uv >/dev/null 2>&1; then
    echo "⚡ Using uv for faster installs ..."
    echo "📥 Installing dependencies ..."
    uv pip install -r requirements.txt
    echo "🤖 Installing qwen-asr ..."
    uv pip install -U qwen-asr
else
    echo "📥 Installing dependencies ..."
    pip install -r requirements.txt
    echo "🤖 Installing qwen-asr ..."
    pip install -U qwen-asr
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "To run the program:"
echo "  source .venv/bin/activate"
echo "  python main.py <file_or_directory> [--audio|--video]"
