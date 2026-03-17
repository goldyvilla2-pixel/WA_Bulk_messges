@echo off
SETLOCAL EnableDelayedExpansion

:: --- CONFIGURATION ---
SET "APP_URL=http://localhost:8000"
SET "PYTHON_REQS=requirements.txt"
SET "BRIDGE_DIR=bridge"

echo ====================================================
echo   🚀 MASTODONITTECH - SMART AUTO-SETUP
echo ====================================================
echo.

:: 1. SMART PYTHON DETECTION
echo [*] Checking for Python...
SET "PYTHON_EXE=python"
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [!] 'python' not found in PATH. Searching common folders...
    FOR /D %%i IN ("%LocalAppData%\Programs\Python\Python*") DO (
        IF EXIST "%%i\python.exe" (
            SET "PYTHON_EXE=%%i\python.exe"
            echo [OK] Found Python at: %%i
            GOTO :PYTHON_FOUND
        )
    )
    
    :: Try 'py' launcher
    py --version >nul 2>&1
    IF %ERRORLEVEL% EQU 0 (
        SET "PYTHON_EXE=py"
        echo [OK] Using Python Launcher 'py'
        GOTO :PYTHON_FOUND
    )

    echo.
    echo ❌ ERROR: Python not detected!
    echo ----------------------------------------------------
    echo To fix this:
    echo 1. Download Python from: https://www.python.org/downloads/
    echo 2. RUN the installer and **Check the box: "Add Python to PATH"**
    echo 3. If already installed, please Re-install and check that box.
    echo ----------------------------------------------------
    pause
    exit /b
)
:PYTHON_FOUND

:: 2. SMART NODE.JS DETECTION
echo [*] Checking for Node.js...
SET "NODE_EXE=node"
node --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [!] 'node' not found in PATH. Searching common folders...
    IF EXIST "C:\Program Files\nodejs\node.exe" (
        SET "NODE_EXE=C:\Program Files\nodejs\node.exe"
        echo [OK] Found Node.js at: C:\Program Files\nodejs
    ) ELSE IF EXIST "%ProgramFiles(x86)%\nodejs\node.exe" (
        SET "NODE_EXE=%ProgramFiles(x86)%\nodejs\node.exe"
        echo [OK] Found Node.js at: %ProgramFiles(x86)%\nodejs
    ) ELSE (
        echo.
        echo ❌ ERROR: Node.js not detected!
        echo ----------------------------------------------------
        echo To fix this:
        echo 1. Download Node.js from: https://nodejs.org/ (LTS Version)
        echo 2. Run the installer and click 'Next' until finished.
        echo 3. Restart your computer if it still fails.
        echo ----------------------------------------------------
        pause
        exit /b
    )
)

:: 3. Install Python Dependencies
echo.
echo [1/3] Checking Python dependencies...
"%PYTHON_EXE%" -m pip install -r %PYTHON_REQS% --quiet
IF %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Dependency check failed. Trying force install...
    "%PYTHON_EXE%" -m pip install fastapi uvicorn python-multipart pandas requests openpyxl pdfplumber --quiet
)

:: 4. Install Node.js Dependencies
echo [2/3] Checking Node.js bridge dependencies...
IF EXIST "%BRIDGE_DIR%\node_modules" (
    echo [OK] Bridge ready.
) ELSE (
    echo [!] Installing bridge components (please wait)...
    pushd %BRIDGE_DIR%
    call npm install --no-fund --no-audit --quiet
    popd
)

:: 5. Launch the Application
echo [3/3] Starting Engine and Launching UI...

:: Start the Python server
start "WATI Backend" /min "%PYTHON_EXE%" main.py

:: Wait for initialization
timeout /t 5 /nobreak >nul

:: Launch Dashboard
start %APP_URL%

echo.
echo ====================================================
echo   ✅ ENGINE RUNNING SUCCESSFULLY! 
echo ====================================================
echo   - App URL: %APP_URL%
echo   - Status: Connected
echo.
echo   Keep this window open. Press any key to stop all.
echo ====================================================
pause

:: Cleanup on exit
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM node.exe /T >nul 2>&1
exit
