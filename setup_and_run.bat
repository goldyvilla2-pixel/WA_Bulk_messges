@echo off
SETLOCAL EnableDelayedExpansion

:: --- CONFIGURATION ---
SET "APP_URL=http://localhost:8000"
SET "PYTHON_REQS=requirements.txt"
SET "BRIDGE_DIR=bridge"

echo ====================================================
echo   🚀 MASTODONITTECH (WA Bulk Message Shooter)
echo ====================================================

:: 1. Check for Python
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python and check "Add to PATH".
    pause
    exit /b
)

:: 2. Check for Node.js
node --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js is not installed.
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b
)

:: 3. Install Python Dependencies
echo [1/3] Checking Python dependencies...
pip install -r %PYTHON_REQS% --quiet
IF %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Some Python dependencies failed to install.
)

:: 4. Install Node.js Dependencies (The Bridge)
echo [2/3] Checking Node.js bridge dependencies...
IF EXIST "%BRIDGE_DIR%\node_modules" (
    echo Node modules already exist, skipping install...
) ELSE (
    pushd %BRIDGE_DIR%
    call npm install --no-fund --no-audit
    popd
)

:: 5. Launch the Application & Browser
echo [3/3] Starting Engine and Launching UI...

:: Start the Python server in a new minimized window
start "WATI Backend" /min python main.py

:: Wait a few seconds for server to initialize
timeout /t 5 /nobreak >nul

:: Launch Chrome to the app URL
echo Launching Google Chrome...
start chrome %APP_URL%

echo.
echo ====================================================
echo   ✅ ENGINE RUNNING! 
echo ====================================================
echo   Keep this window open while using the app.
echo   To stop, simply close this window and the server.
echo ====================================================
echo.

:: Keep the window alive to show logs or errors
pause
