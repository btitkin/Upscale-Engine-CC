@echo off
chcp 65001 >nul
title Upscale Engine CC - First Run Setup

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║         Upscale Engine CC - First Run Setup                  ║
echo ╠══════════════════════════════════════════════════════════════╣
echo ║  This will install all required dependencies:                ║
echo ║  - Python packages                                           ║
echo ║  - PyTorch with CUDA                                         ║
echo ║  - ComfyUI and custom nodes                                  ║
echo ║  - Required AI models (~15 GB download)                      ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo Press any key to start installation or Ctrl+C to cancel...
pause >nul

echo.
echo [1/2] Setting up Python virtual environment...
echo.

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        echo Please ensure Python 3.10+ is installed.
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo [2/2] Running dependency installer...
echo.

python backend\install_dependencies.py

if errorlevel 1 (
    echo.
    echo ══════════════════════════════════════════════════════════════
    echo   Some dependencies could not be installed.
    echo   Please check the errors above and run this script again.
    echo ══════════════════════════════════════════════════════════════
) else (
    echo.
    echo ══════════════════════════════════════════════════════════════
    echo   ✓ Installation complete!
    echo.
    echo   To start the application:
    echo   - Double-click START_UPSCALE_ENGINE.bat
    echo ══════════════════════════════════════════════════════════════
)

echo.
pause
