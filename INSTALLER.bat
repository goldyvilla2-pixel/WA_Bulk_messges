@echo off
SETLOCAL EnableDelayedExpansion

echo ====================================================
echo   🛠️ MASTODONITTECH - PREREQUISITES INSTALLER
echo ====================================================
echo.

:: 1. Check for Python
echo [1/4] Checking for Python...
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed. 
    echo Please download and install from https://www.python.org/
    echo ** IMPORTANT: Check the box "Add Python to PATH" during installation. **
    pause
    exit /b
)
echo Status: OK

:: 2. Check for Node.js
echo [2/4] Checking for Node.js...
node --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js is not installed.
    echo Please download and install from https://nodejs.org/
    pause
    exit /b
)
echo Status: OK

:: 3. Install Python Requirements
echo [3/4] Checking Python packages (requirements.txt)...
:: We use pip's internal check to avoid re-downloading everything
pip install -r requirements.txt --upgrade-strategy only-if-needed
IF %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Some Python packages could not be installed. 
    echo Check your internet connection and try again.
)
echo Status: OK

:: 4. Install Node.js Requirements
echo [4/4] Checking Node.js bridge dependencies...
IF EXIST "bridge\node_modules" (
    echo Node modules already present. Verifying...
    pushd bridge
    call npm install --no-fund --no-audit
    popd
) ELSE (
    echo Installing node modules for the first time...
    pushd bridge
    call npm install --no-fund --no-audit
    popd
)
echo Status: OK

echo.
echo ====================================================
echo   ✅ ALL REQUIREMENTS ARE READY!
echo ====================================================
echo   You can now run the app using 'setup_and_run.bat'
echo ====================================================
echo.
pause
