@echo off
setlocal enabledelayedexpansion

echo.
echo ════════════════════════════════════════════════
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo ❌ Virtual environment not found.
    echo Please run windows_install.bat first.
    pause
    exit /b 1
)

echo 🚀 Starting Subgen GUI ...
echo.
echo ════════════════════════════════════════════════
echo.

call .venv\Scripts\activate.bat

echo 📦 Ensuring dependencies are installed ...
pip install -r requirements.txt

echo.
echo 🚀 Launching Subgen GUI ...
echo.
python main.py

if !errorlevel! neq 0 (
    echo.
    echo ❌ Program exited with an error.
    pause
)

endlocal
