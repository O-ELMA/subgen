@echo off
setlocal enabledelayedexpansion

echo.
echo ════════════════════════════════════════════════
echo.

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
    goto :error
)

for /f "tokens=*" %%V in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VERSION=%%V
if !errorlevel! neq 0 goto :error
echo 🐍 Found %PYTHON_VERSION% (using %PYTHON_CMD%)

echo.
echo ════════════════════════════════════════════════
echo.

REM Create virtual environment
echo 📦 Creating virtual environment (.venv) ...
%PYTHON_CMD% -m venv .venv || goto :error

echo.
echo ════════════════════════════════════════════════
echo.

REM Activate
call .venv\Scripts\activate.bat || goto :error

echo.
echo ════════════════════════════════════════════════
echo.

REM Upgrade pip
echo ⬆️  Upgrading pip ...
python -m pip install --upgrade pip || goto :error

echo.
echo ════════════════════════════════════════════════
echo.

REM Install dependencies
echo 📥 Installing dependencies ...
pip install -r requirements.txt || goto :error

echo.
echo ════════════════════════════════════════════════
echo.

REM Install torch (CPU only)
echo 🔥 Installing torch (CPU only) ...
pip install torch --index-url https://download.pytorch.org/whl/cpu || goto :error

echo.
echo ════════════════════════════════════════════════
echo.

REM Install qwen-asr
echo 🤖 Installing qwen-asr ...
pip install -U qwen-asr || goto :error

echo.
echo ════════════════════════════════════════════════
echo.

REM Setup .env if missing
if not exist .env (
    echo.
    echo ════════════════════════════════════════════════
    echo.
    echo Paste your NanoGPT API key (leave empty to skip):
    set /p USER_KEY=
    if defined USER_KEY (
        echo NANO_GPT_KEY=%USER_KEY%> .env
    ) else (
        echo NANO_GPT_KEY=> .env
    )
)

echo.
echo ════════════════════════════════════════════════
echo.

echo.
echo ✅ Installation complete!
echo.
echo To run the program:
echo   .venv\Scripts\activate.bat
echo   python main.py ^<file_or_directory^> [--audio^|--video]
goto :end

:error
echo.
echo ❌ Installation failed.
pause

:end
endlocal
