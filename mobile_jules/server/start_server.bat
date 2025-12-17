@echo off
:: Mobile Jules Server Startup Script

:: ==========================================
:: CONFIGURATION SECTION - EDIT THIS!
:: ==========================================

:: 1. Your Google/Jules API Key
set GOOGLE_API_KEY="REDACTED_API_KEY"

:: 2. The full path to your 'mobile_jules/server' folder
:: Example: C:\Users\Alice\Documents\jules-mobile-wrapper\mobile_jules\server
cd /d "C:\PATH\TO\YOUR\jules-mobile-wrapper\mobile_jules\server"

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

python -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
