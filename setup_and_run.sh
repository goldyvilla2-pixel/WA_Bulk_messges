#!/bin/bash

# --- CONFIGURATION ---
APP_URL="http://localhost:8000"
PYTHON_REQS="requirements.txt"
BRIDGE_DIR="bridge"

echo "===================================================="
echo "  🚀 MASTODONITTECH - SMART AUTO-SETUP (macOS/Linux)"
echo "===================================================="
echo ""

# 1. SMART PYTHON DETECTION
echo "[*] Checking for Python..."
if command -v python3 &>/dev/null; then
    PYTHON_EXE="python3"
elif command -v python &>/dev/null; then
    PYTHON_EXE="python"
else
    echo "❌ ERROR: Python not detected!"
    echo "Please install Python from https://www.python.org/"
    exit 1
fi
echo "[OK] Using: $($PYTHON_EXE --version)"

# 2. SMART NODE.JS DETECTION
echo "[*] Checking for Node.js..."
if ! command -v node &>/dev/null; then
    echo "❌ ERROR: Node.js not detected!"
    echo "Please install Node.js (LTS Version) from https://nodejs.org/"
    exit 1
fi
echo "[OK] Using Node: $(node --version)"

# 3. Install Python Dependencies
echo ""
echo "[1/3] Checking Python dependencies..."
$PYTHON_EXE -m pip install -r "$PYTHON_REQS" --quiet
if [ $? -ne 0 ]; then
    echo "[WARNING] Dependency check failed. Trying force install..."
    $PYTHON_EXE -m pip install fastapi uvicorn python-multipart pandas requests openpyxl pdfplumber --quiet
fi

# 4. Install Node.js Dependencies
echo "[2/3] Checking Node.js bridge dependencies..."
if [ -d "$BRIDGE_DIR/node_modules" ]; then
    echo "[OK] Bridge ready."
else
    echo "[!] Installing bridge components (please wait)..."
    cd "$BRIDGE_DIR" || exit
    npm install --no-fund --no-audit --quiet
    cd ..
fi

# 5. Launch the Application
echo "[3/3] Starting Engine and Launching UI..."

# Start the Python server in the background
$PYTHON_EXE main.py &
PY_PID=$!

# Wait for initialization
sleep 5

# Launch Dashboard
if command -v open &>/dev/null; then
    open "$APP_URL" # macOS
elif command -v xdg-open &>/dev/null; then
    xdg-open "$APP_URL" # Linux
fi

echo ""
echo "===================================================="
echo "  ✅ ENGINE RUNNING SUCCESSFULLY!" 
echo "===================================================="
echo "  - App URL: $APP_URL"
echo "  - Status: Connected"
echo ""
echo "  Press CTRL+C to stop the server."
echo "===================================================="

# Keep script running to manage the background process
wait $PY_PID
