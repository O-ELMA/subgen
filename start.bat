@echo off
setlocal enabledelayedexpansion

echo.
echo ________________________________________________
echo.

REM Find a suitable Python interpreter
set PYTHON_CMD=
for %%C in (python python3 py) do (
    where %%C >nul 2>&1
    if !errorlevel! equ 0 (
        set PYTHON_CMD=%%C
        goto :found_python
    )
)

:found_python
if "%PYTHON_CMD%"=="" (
    echo ❌ Error: Python is not installed. Please install Python 3.12 or higher.
    pause
    exit /b 1
)

for /f "tokens=*" %%V in ('%PYTHON_CMD% --version 2^>^&1') do set PYTHON_VERSION=%%V
echo 🐍 Found %PYTHON_VERSION% (using %PYTHON_CMD%)

REM Bootstrap virtual environment if missing
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo ________________________________________________
    echo.
    echo 📦 Creating virtual environment (.venv) ...
    %PYTHON_CMD% -m venv .venv || goto :error

    echo.
    echo ________________________________________________
    echo.

    call .venv\Scripts\activate.bat || goto :error

    echo ⬆️  Upgrading pip ...
    python -m pip install --upgrade pip || goto :error

    echo.
    echo ________________________________________________
    echo.

    echo 📥 Installing dependencies ...
    pip install -r requirements.txt || goto :error

    echo.
    echo ________________________________________________
    echo.

    echo 🔥 Installing torch (CPU only) ...
    pip install torch --index-url https://download.pytorch.org/whl/cpu || goto :error

    echo.
    echo ________________________________________________
    echo.

    echo 🤖 Installing qwen-asr ...
    pip install -U qwen-asr || goto :error

    echo.
    echo ________________________________________________
    echo.

    REM Setup .env if missing
    if not exist .env (
        echo Paste your NanoGPT API key (leave empty to skip):
        set /p USER_KEY=
        if defined USER_KEY (
            echo NANO_GPT_KEY=%USER_KEY%> .env
        ) else (
            echo NANO_GPT_KEY=> .env
        )
    )
)

echo.
echo ________________________________________________
echo.

call .venv\Scripts\activate.bat

echo 📦 Ensuring dependencies are up to date ...
pip install -r requirements.txt

echo.
echo ________________________________________________
echo.

REM Check for NanoGPT API key
set NANO_KEY_FOUND=
if exist .env (
    for /f "tokens=1,* delims==" %%A in (.env) do (
        if "%%A"=="NANO_GPT_KEY" if not "%%B"=="" set NANO_KEY_FOUND=1
    )
)

if not defined NANO_KEY_FOUND (
    echo Paste your NanoGPT API key (leave empty to skip):
    set /p USER_KEY=
    if defined USER_KEY (
        echo NANO_GPT_KEY=%USER_KEY%> .env
    ) else (
        echo NANO_GPT_KEY=> .env
    )
    echo.
    echo ________________________________________________
    echo.
)

echo 🚀 Launching Subgen GUI ...
echo.
python main.py

if !errorlevel! neq 0 (
    echo.
    echo ❌ Program exited with an error.
    pause
)

endlocal
exit /b 0

:error
echo.
echo ❌ An error occurred.
pause
endlocal
exit /b 1
