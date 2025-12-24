@echo off
:: Mobile Jules Server Startup Script
:: ==========================================
:: This script reads configuration from environment variables.
:: Set JULES_API_KEY in your system environment or create a
:: 'set_env.bat' file (gitignored) with: set JULES_API_KEY=your_key_here
:: ==========================================

:: Load local environment if exists (this file should NOT be committed)
if exist "%~dp0set_env.bat" call "%~dp0set_env.bat"

:: Check if API key is set
if "%JULES_API_KEY%"=="" (
    echo ERROR: JULES_API_KEY is not set!
    echo Please either:
    echo   1. Set JULES_API_KEY as a system environment variable, OR
    echo   2. Create 'set_env.bat' in this folder with: set JULES_API_KEY=your_key
    pause
    exit /b 1
)

:: Change to script directory
cd /d "%~dp0"

:: ==========================================
:: END CONFIGURATION
:: ==========================================

echo Starting Mobile Jules Server...
set PYTHONPATH=%PYTHONPATH%;..

:: Check if python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found! Please ensure Python is installed and in your PATH.
    pause
    exit /b
)

:: Run main.py directly to enable ngrok tunnel startup
python main.py
pause
