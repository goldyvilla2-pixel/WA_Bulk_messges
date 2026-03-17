# 🚀 MASTODONITTECH - SETUP GUIDE

Follow these instructions to get your WhatsApp Bulk Message tool running on your computer.

---

## 💻 WINDOWS SETUP (PC/Laptop)

### 1️⃣ Initial Prerequisites
1.  **Download Python**: [python.org/downloads](https://www.python.org/downloads/)
    *   **CRITICAL**: During installation, you **MUST** check the box that says **"Add Python to PATH"**.
2.  **Download Node.js**: [nodejs.org](https://nodejs.org/) (Download the **LTS** version).
    *   Click "Next" until finished. No special settings needed.

### 2️⃣ How to Run
1.  Open your project folder (`BulkWATItoll`).
2.  **Double-click `INSTALLER.bat`**: This will install all required libraries.
3.  **Double-click `setup_and_run.bat`**: This starts the app.
4.  A browser window will open at `http://localhost:8000`.

---

## 🍎 MACBOOK SETUP (macOS)

### 1️⃣ Initial Prerequisites
1.  **Download Python**: [python.org/downloads](https://www.python.org/downloads/)
    *   Run the installer. Mac does not have a "PATH" checkbox.
2.  **Download Node.js**: [nodejs.org](https://nodejs.org/) (Download the **LTS** version).
    *   Run the installer.

### 2️⃣ First-Time Activation (One-Time Only)
Mac needs permission to run the launcher. 
1.  Open **Terminal** (Press `Command + Space` and type `Terminal`).
2.  Copy and Paste this exact line into Terminal and press **Enter**:
    ```bash
    chmod +x ~/Downloads/BulkWATItoll/RUN_ME.command
    ```

### 3️⃣ How to Run
1.  Open your project folder.
2.  **Double-click `RUN_ME.command`**.
3.  It will automatically start the engine and open the dashboard.

---

## 🛠️ TROUBLESHOOTING

### My .bat or .command file closes immediately!
*   **Windows**: Right-click inside the folder, select "Open in Terminal", type `setup_and_run.bat` and press Enter to see the error.
*   **Mac**: If it says "identified developer" error, go to **System Settings > Privacy & Security** and click **"Open Anyway"** at the bottom.

### WhatsApp QR code not showing?
*   Wait about 10-15 seconds for the backend to initialize.
*   Ensure your internet connection is active.
*   Make sure you have Chrome browser installed.

---
*Created for BulkWATItoll Project*
