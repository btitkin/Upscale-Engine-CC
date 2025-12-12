@echo off
echo ========================================
echo    Upscale Engine CC - Install Dependencies
echo ========================================
echo.

REM Check if in correct directory
if not exist "package.json" (
    echo ERROR: Please run this from the upscale engine project directory!
    pause
    exit /b 1
)

echo This will check and install all dependencies.
echo Including: PyTorch, ComfyUI, Custom Nodes, Models
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause > nul

echo.
echo [*] Starting dependency installation...
echo.

cd backend
call .venv\Scripts\activate
python -c "from install_dependencies import check_and_install_dependencies; check_and_install_dependencies()"

echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo You can now run START_UPSCALE_ENGINE.bat
echo.
pause
