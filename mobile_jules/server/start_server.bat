@echo off
:: Mobile Jules Server Startup Script

:: ==========================================
:: CONFIGURATION SECTION - EDIT THIS!
:: ==========================================

:: 1. Your Google/Jules API Key
set GOOGLE_API_KEY="AQ.Ab8RN6KKEiLic-GInn3szRXG_fyX881-pHm10Mpk_cueHsVA0Q"

:: ==========================================
:: END CONFIGURATION
:: ==========================================

echo Starting Mobile Jules Server...

:: Switch to the directory where this script is located
cd /d "%~dp0"

:: Add parent directory to PYTHONPATH so jules_client can be imported if needed
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
