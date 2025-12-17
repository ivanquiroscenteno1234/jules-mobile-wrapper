@echo off
:: Mobile Jules Server Startup Script

:: ==========================================
:: CONFIGURATION SECTION - EDIT THIS!
:: ==========================================

:: 1. Your Google/Jules API Key
:: Replace the text below with your actual key (starts with AIza...)
set GOOGLE_API_KEY=YOUR_KEY_HERE

:: ==========================================
:: END CONFIGURATION
:: ==========================================

:: Automatically navigate to the folder containing this script
cd /d "%~dp0"

echo Starting Mobile Jules Server...

:: Check for API Key
if "%GOOGLE_API_KEY%"=="YOUR_KEY_HERE" (
    echo.
    echo [ERROR] You have not set your Google API Key yet!
    echo 1. Right-click 'start_server.bat' and select 'Edit'.
    echo 2. Replace 'YOUR_KEY_HERE' with your actual key.
    echo.
    pause
    exit /b
)

:: Add parent directory to python path
set PYTHONPATH=%PYTHONPATH%;..\..

:: Check if python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found! Please ensure Python is installed and in your PATH.
    pause
    exit /b
)

:: Run the python script directly (this ensures the Ngrok logic in main.py runs)
python main.py
pause
