@echo off
setlocal enabledelayedexpansion

REM Find a suitable Python interpreter
set PYTHON_CMD=
for %%C in (python python3 py) do (
    where %%C >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=%%C
        goto :found
    )
)

:found
if "%PYTHON_CMD%"=="" (
    echo ❌ Error: Python is not installed. Please install Python 3.12 or higher.
    exit /b 1
)

for /f "tokens=*" %%V in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VERSION=%%V
echo 🐍 Found %PYTHON_VERSION% (using %PYTHON_CMD%)

REM Create virtual environment
echo 📦 Creating virtual environment (.venv) ...
%PYTHON_CMD% -m venv .venv

REM Activate
call .venv\Scripts\activate.bat

REM Upgrade pip
echo ⬆️  Upgrading pip ...
python -m pip install --upgrade pip

REM Install dependencies
echo 📥 Installing dependencies ...
pip install -r requirements.txt

REM Install qwen-asr
echo 🤖 Installing qwen-asr ...
pip install -U qwen-asr

echo.
echo ✅ Installation complete!
echo.
echo To run the program:
echo   .venv\Scripts\activate.bat
echo   python main.py ^<file_or_directory^> [--audio^|--video]
