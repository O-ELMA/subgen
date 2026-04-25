#!/usr/bin/env bash

run() {
    set -e

    echo ""
    echo "════════════════════════════════════════════════"
    echo ""

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

    echo ""
    echo "════════════════════════════════════════════════"
    echo ""

    echo "📦 Creating virtual environment (.venv) ..."
    $PYTHON_CMD -m venv .venv

    echo ""
    echo "════════════════════════════════════════════════"
    echo ""

    source .venv/bin/activate

    if command -v uv >/dev/null 2>&1; then
        echo "⚡ Using uv for faster installs ..."
        echo ""
        echo "════════════════════════════════════════════════"
        echo ""
        echo "📥 Installing dependencies ..."
        uv pip install -r requirements.txt
        echo ""
        echo "════════════════════════════════════════════════"
        echo ""
        echo "🔥 Installing torch (CPU only) ..."
        uv pip install torch --index-url https://download.pytorch.org/whl/cpu
        echo ""
        echo "════════════════════════════════════════════════"
        echo ""
        echo "🤖 Installing qwen-asr ..."
        uv pip install -U qwen-asr --torch-backend=cpu
    else
        echo "📥 Installing dependencies ..."
        pip install -r requirements.txt
        echo ""
        echo "════════════════════════════════════════════════"
        echo ""
        echo "🔥 Installing torch (CPU only) ..."
        pip install torch --index-url https://download.pytorch.org/whl/cpu
        echo ""
        echo "════════════════════════════════════════════════"
        echo ""
        echo "🤖 Installing qwen-asr ..."
        pip install -U qwen-asr --torch-backend=cpu
    fi

    echo ""
    echo "════════════════════════════════════════════════"
    echo ""

    echo ""
    echo "✅ Installation complete!"
    echo ""
    echo "To run the program:"
    echo "  source .venv/bin/activate"
    echo "  python main.py <file_or_directory> [--audio|--video]"
}

run
exit_code=$?
if [ $exit_code -ne 0 ]; then
    echo ""
    echo "❌ Installation failed."
    read -p "Press Enter to close..."
fi
exit $exit_code
