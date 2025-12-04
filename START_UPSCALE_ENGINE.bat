@echo off
echo ========================================
echo    Upscale Engine CC - One-Click Launcher
echo ========================================
echo.

REM Check if in correct directory
if not exist "package.json" (
    echo ERROR: Please run this from the upscale engine project directory!
    pause
    exit /b 1
)

echo [1/2] Starting Python Backend...
echo.

REM Start backend in background
start "Upscale Engine Backend" cmd /k "cd backend && .venv\Scripts\activate && python server.py"

REM Wait for backend to be ready
timeout /t 3 /nobreak > nul

echo [2/2] Starting Electron App...
echo.

REM Start Electron frontend
call npm run electron:dev

REM Clean up when Electron closes
echo.
echo Upscale Engine CC closed. Press any key to exit.
pause > nul
