@echo off
REM LumaScale Backend Launcher for Windows
REM Automatically sets up Python environment and starts server

echo ========================================
echo LumaScale Backend Server
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

echo Python found: 
python --version
echo.

REM Check for virtual environment
if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Using virtual environment (.venv)
    call .venv\Scripts\activate.bat
    echo.
) else (
    echo [INFO] No virtual environment found - using system Python
    echo [TIP] For isolated environment, run LAUNCH_LUMASCALE.bat instead
    echo.
)

REM Check if requirements are installed
python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing Python dependencies...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    echo.
)

REM Check for models
python -c "from pathlib import Path; import sys; sys.exit(0 if (Path('../models/4x-UltraSharp.pth').exists()) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo  MODELS NOT FOUND
    echo ========================================
    echo First-time setup detected.
    echo Models will be downloaded automatically on first API call,
    echo OR you can download them now manually:
    echo.
    set /p download="Download models now? (y/n): "
    if /i "%download%"=="y" (
        python model_downloader.py
    )
    echo.
)

echo ========================================
echo Starting Flask server on port 5555...
echo ========================================
echo.

python server.py

pause
