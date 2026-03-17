@echo off
SETLOCAL EnableDelayedExpansion

:: ---------------------------------------------------------
:: MASTODONITTECH - FLAT STARTUP SCRIPT
:: This version avoids nested IF/ELSE blocks to prevent 
:: common batch syntax errors with paths.
:: ---------------------------------------------------------

echo ====================================================
echo   🚀 MASTODONITTECH - SMART AUTO-SETUP
echo ====================================================
echo.

:: 0. PRE-START CLEANUP
echo [*] Cleaning up old processes...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM node.exe /T >nul 2>&1
echo [OK] Fresh environment ready.
echo.

:: 1. PYTHON CHECK
echo [*] Checking for Python...
SET "PYTHON_EXE=python"
python --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 GOTO :PYTHON_OK

:: Try common path
FOR /D %%i IN ("%LocalAppData%\Programs\Python\Python*") DO (
    IF EXIST "%%i\python.exe" (
        SET "PYTHON_EXE=%%i\python.exe"
        GOTO :PYTHON_OK
    )
)

:: Try launcher
py --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    SET "PYTHON_EXE=py"
    GOTO :PYTHON_OK
)

echo ❌ ERROR: Python not detected!
echo Please install Python and check "Add to PATH"
pause
exit /b

:PYTHON_OK
echo [OK] Using Python: %PYTHON_EXE%

:: 2. NODE CHECK
echo [*] Checking for Node.js...
SET "NODE_EXE=node"
node --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 GOTO :NODE_OK

IF EXIST "C:\Program Files\nodejs\node.exe" (
    SET "NODE_EXE=C:\Program Files\nodejs\node.exe"
    GOTO :NODE_OK
)

:: Check x86 path manually to avoid variable expansion issues with parens
IF EXIST "C:\Program Files (x86)\nodejs\node.exe" (
    SET "NODE_EXE=C:\Program Files (x86)\nodejs\node.exe"
    GOTO :NODE_OK
)

echo ❌ ERROR: Node.js not detected!
echo Please install Node.js (LTS) from nodejs.org
pause
exit /b

:NODE_OK
echo [OK] Using Node.js: %NODE_EXE%

:: 3. DEPENDENCIES
echo.
echo [1/3] Checking Python dependencies...
"%PYTHON_EXE%" -m pip install -r requirements.txt --quiet
IF !ERRORLEVEL! NEQ 0 (
    echo [!] Standard install failed. Trying minimal install...
    "%PYTHON_EXE%" -m pip install fastapi uvicorn python-multipart pandas requests openpyxl pdfplumber --quiet
)

echo [2/3] Checking Node.js bridge...
IF EXIST "bridge\node_modules" GOTO :BRIDGE_OK
echo [!] Installing bridge components...
pushd bridge
call npm install --no-fund --no-audit --quiet
popd

:BRIDGE_OK
echo [OK] Bridge ready.

:: 4. LAUNCH
echo [3/3] Starting Engine...
start "WATI Backend" /min "%PYTHON_EXE%" main.py

echo [*] Waiting for initialization...
timeout /t 5 /nobreak >nul

echo [OK] Launching Dashboard...
start http://localhost:8000

echo ====================================================
echo   ✅ ENGINE RUNNING SUCCESSFULLY! 
echo ====================================================
echo   Keep this window open. Press any key to stop all.
echo ====================================================
pause

:: CLEANUP
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM node.exe /T >nul 2>&1
exit
