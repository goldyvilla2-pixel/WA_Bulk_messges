#!/bin/zsh

# ---------------------------------------------------------
# MASTODONITTECH - MAC ONE-CLICK LAUNCHER
# ---------------------------------------------------------

# 1. Go to the folder where this file is saved
cd "$(dirname "$0")"

echo "===================================================="
echo "  🚀 MASTODONITTECH - MAC LAUNCHER"
echo "===================================================="

# 2. Check for Python
if command -v python3 &>/dev/null; then
    PYTHON_EXE="python3"
elif command -v python &>/dev/null; then
    PYTHON_EXE="python"
else
    echo "❌ ERROR: Python not found."
    echo "Please install Python from python.org"
    read -n 1 -s -r -p "Press any key to exit..."
    exit 1
fi

# 3. Check for Node.js
if ! command -v node &>/dev/null; then
    echo "❌ ERROR: Node.js not found."
    echo "Please install Node.js from nodejs.org"
    read -n 1 -s -r -p "Press any key to exit..."
    exit 1
fi

# 4. Install dependencies (Quick check)
echo "[*] Verifying requirements..."
$PYTHON_EXE -m pip install -r requirements.txt --quiet

if [ ! -d "bridge/node_modules" ]; then
    echo "[*] Installing bridge components (one-time setup)..."
    cd bridge && npm install --quiet && cd ..
fi

# 5. Start App
echo "[*] Starting Engine..."
$PYTHON_EXE main.py &
PY_PID=$!

# 6. Open Browser
sleep 5
open "http://localhost:8000"

echo "✅ App is Running!"
echo "----------------------------------------------------"
echo "Keep this window open while using the app."
echo "To stop, close this window or press CTRL+C."
echo "----------------------------------------------------"

# Wait for the python process
wait $PY_PID
