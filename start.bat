@echo off
setlocal enabledelayedexpansion
title Subgen Setup

REM Ensure we are in the script's directory
cd /d "%~dp0"

REM Verify required files exist
if not exist "requirements.txt" (
    echo Error: requirements.txt not found.
    echo Please run this script from the subgen folder.
    pause
    exit /b 1
)
if not exist "main.py" (
    echo Error: main.py not found.
    echo Please run this script from the subgen folder.
    pause
    exit /b 1
)

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
    echo Error: Python is not installed or not in PATH.
    echo Please install Python 3.10 - 3.13 from https://python.org
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%V in ('%PYTHON_CMD% --version 2^>^&1') do set PY_VER=%%V
for /f "tokens=1,2 delims=." %%A in ("%PY_VER%") do (
    set PY_MAJOR=%%A
    set PY_MINOR=%%B
)

echo Found Python %PY_VER% (using %PYTHON_CMD%)

if %PY_MAJOR% lss 3 (
    echo Error: Python 3 is required.
    pause
    exit /b 1
)
if %PY_MINOR% lss 10 (
    echo Error: Python 3.10 or higher is required.
    pause
    exit /b 1
)
if %PY_MINOR% gtr 13 (
    echo Warning: Python 3.%PY_MINOR% is very new and may lack package support.
    echo Consider installing Python 3.12 or 3.13 for best compatibility.
    echo.
    echo Press any key to continue anyway, or close this window to cancel.
    pause >nul
)

REM Verify venv module is available
%PYTHON_CMD% -c "import venv" >nul 2>&1
if !errorlevel! neq 0 (
    echo Error: Python venv module is missing.
    echo Please reinstall Python and check "Add Python to PATH" and "Install pip".
    pause
    exit /b 1
)

REM Bootstrap virtual environment if missing
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo ________________________________________________
    echo.
    echo Creating virtual environment ^(.venv^) ...
    %PYTHON_CMD% -m venv .venv
    if !errorlevel! neq 0 (
        echo Error: Failed to create virtual environment.
        echo If your Windows username contains spaces or special characters,
        echo try moving this folder to C:\subgen\ and run again.
        pause
        exit /b 1
    )

    echo.
    echo ________________________________________________
    echo.

    call .venv\Scripts\activate.bat
    if !errorlevel! neq 0 (
        echo Error: Failed to activate virtual environment.
        pause
        exit /b 1
    )

    echo Upgrading pip ...
    python -m pip install --upgrade pip
    if !errorlevel! neq 0 (
        echo Error: Failed to upgrade pip. Check your internet connection.
        pause
        exit /b 1
    )

    echo.
    echo ________________________________________________
    echo.

    echo Installing dependencies ...
    pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo Error: Failed to install dependencies. Check your internet connection.
        pause
        exit /b 1
    )

    echo.
    echo ________________________________________________
    echo.

    echo Installing torch ^(CPU only^) ...
    pip install torch --index-url https://download.pytorch.org/whl/cpu
    if !errorlevel! neq 0 (
        echo Error: Failed to install torch. Check your internet connection.
        pause
        exit /b 1
    )

    echo.
    echo ________________________________________________
    echo.

    echo Installing qwen-asr ...
    pip install -U qwen-asr
    if !errorlevel! neq 0 (
        echo Error: Failed to install qwen-asr. Check your internet connection.
        pause
        exit /b 1
    )

    echo.
    echo ________________________________________________
    echo.

    REM Setup .env if missing
    if not exist .env (
        echo Paste your NanoGPT API key ^(leave empty to skip^):
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

echo Ensuring dependencies are up to date ...
pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo Warning: Dependency update failed. Continuing anyway ...
)

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
    echo Paste your NanoGPT API key ^(leave empty to skip^):
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

echo Launching Subgen GUI ...
echo.
set PYTHONIOENCODING=utf-8
python main.py

if !errorlevel! neq 0 (
    echo.
    echo Program exited with an error.
    pause
)

endlocal
exit /b 0
