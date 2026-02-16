import os
import time
import random
import logging
import shutil
import io
import subprocess
import requests
import uuid
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pandas as pd

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directories
UPLOAD_DIR = os.path.abspath("uploads")
BRIDGE_DIR = os.path.abspath("bridge")
SESSION_DIR = os.path.abspath(os.path.join("bridge", ".wwebjs_auth"))

def ensure_dirs():
    for d in [UPLOAD_DIR, BRIDGE_DIR]:
        os.makedirs(d, exist_ok=True)

# Global status tracking
sending_status = {
    "is_running": False,
    "current_index": 0,
    "total": 0,
    "success": 0,
    "failed": 0,
    "logs": [],
    "step": "idle", # idle, waiting_for_qr, sending, finished
    "qr_code": None,
    "connected_user": None
}

bridge_process = None

def start_bridge():
    global bridge_process
    try:
        # Check if already running
        requests.get("http://localhost:3001/status", timeout=1)
        logger.info("Bridge is already running.")
    except:
        logger.info("Starting WhatsApp Bridge...")
        log_file = open("bridge_log.txt", "w")
        bridge_process = subprocess.Popen(
            ["node", "bridge.js"],
            cwd=BRIDGE_DIR,
            stdout=log_file,
            stderr=log_file,
            text=True
        )

# Mount static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("frontend/index.html")

@app.get("/status")
async def get_status():
    global sending_status
    # Check bridge for QR if we are in waiting state
    try:
        bridge_resp = requests.get("http://localhost:3001/status", timeout=1).json()
        if bridge_resp.get("ready"):
            sending_status["step"] = "sending" if sending_status["is_running"] else "connected"
            sending_status["qr_code"] = None
            sending_status["connected_user"] = bridge_resp.get("deviceInfo")
        else:
            sending_status["connected_user"] = None
            # Fetch QR if bridge is up but not linked
            qr_resp = requests.get("http://localhost:3001/qr", timeout=1).json()
            if qr_resp.get("qr"):
                sending_status["qr_code"] = qr_resp["qr"]
                sending_status["step"] = "waiting_for_qr"
            else:
                sending_status["step"] = "initializing"
    except:
        # Bridge is likely down, restart it
        logger.warning("Bridge offline, restarting...")
        start_bridge()
        sending_status["step"] = "starting_bridge"
        sending_status["connected_user"] = None
        sending_status["qr_code"] = None
        
    return sending_status

def bulk_send_task(numbers: List[str], message: str, image_path: str, delay: int):
    global sending_status
    sending_status["is_running"] = True
    sending_status["total"] = len(numbers)
    sending_status["logs"] = ["⚡ Initializing Thunder-Link Bridge..."]
    sending_status["step"] = "initializing"
    
    start_bridge()
    
    # Wait for connection
    connected = False
    start_wait = time.time()
    while time.time() - start_wait < 300: # 5 min timeout
        if not sending_status["is_running"]: return
        try:
            resp = requests.get("http://localhost:3001/status", timeout=2).json()
            if resp.get("ready"):
                connected = True
                sending_status["logs"].append("✅ Bridge Connected!")
                sending_status["step"] = "sending"
                break
        except: pass
        time.sleep(3)

    if not connected:
        sending_status["logs"].append("❌ Bridge connection timed out.")
        sending_status["is_running"] = False
        return

    for i, phone in enumerate(numbers):
        if not sending_status["is_running"]: break
        sending_status["current_index"] = i + 1
        sending_status["current_phone"] = phone
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        
        try:
            sending_status["logs"].append(f"📤 Sending to {phone}...")
            payload = {
                "phone": clean_phone,
                "message": message,
                "imagePath": image_path if image_path else None
            }
            resp = requests.post("http://localhost:3001/send", json=payload, timeout=60)
            if resp.status_code == 200:
                sending_status["success"] += 1
                sending_status["logs"].append(f"✅ Sent to {phone}")
            else:
                raise Exception(resp.json().get("error", "Unknown error"))
        except Exception as e:
            sending_status["failed"] += 1
            sending_status["logs"].append(f"⚠️ Failed for {phone}: {str(e)[:50]}")
        
        if i < len(numbers) - 1:
            wait = delay + random.randint(-2, 2)
            time.sleep(max(1, wait))

    sending_status["step"] = "finished"
    sending_status["logs"].append("🏁 Bulk send completed!")
    sending_status["is_running"] = False

@app.post("/start-bulk")
async def start_bulk(
    background_tasks: BackgroundTasks,
    numbers: str = Form(None),
    message: str = Form(...),
    delay: int = Form(20),
    image: UploadFile = File(None),
    csv_file: UploadFile = File(None)
):
    phone_list = []
    
    if csv_file:
        contents = await csv_file.read()
        df = pd.read_csv(io.BytesIO(contents), dtype=str)
        cols_map = {c.lower(): c for c in df.columns}
        
        has_cc = 'country_code' in cols_map or 'cc' in cols_map
        has_phone = 'phone' in cols_map or 'number' in cols_map
        
        if has_cc and has_phone:
            cc_col = cols_map.get('country_code') or cols_map.get('cc')
            ph_col = cols_map.get('phone') or cols_map.get('number')
            for _, row in df.iterrows():
                cc = str(row[cc_col]).strip() if pd.notna(row[cc_col]) else ""
                ph = str(row[ph_col]).strip() if pd.notna(row[ph_col]) else ""
                if not ph or ph.lower() == 'nan': continue
                # Sanitization
                cc = cc.replace('.0', '').replace('+', '')
                ph = ph.replace('.0', '').replace('+', '')
                phone_list.append(f"+{cc}{ph}")
        else:
            # Fallback to first column
            target_col = df.columns[0]
            for n in df[target_col].astype(str).tolist():
                clean_n = n.strip().replace('.0', '')
                if clean_n == 'nan' or not clean_n: continue
                if not clean_n.startswith('+'): clean_n = '+' + clean_n
                phone_list.append(clean_n)

    # Unique list
    final_list = []
    seen = set()
    for p in phone_list:
        if p and p not in seen:
            seen.add(p)
            final_list.append(p)
    
    image_path = ""
    if image and image.filename:
        filename = f"{uuid.uuid4()}_{image.filename}"
        image_path = os.path.join(UPLOAD_DIR, filename)
        with open(image_path, "wb") as f:
            f.write(await image.read())

    background_tasks.add_task(bulk_send_task, final_list, message, image_path, delay)
    return {"status": "started", "total": len(final_list)}

@app.post("/parse-csv")
async def parse_csv(csv_file: UploadFile = File(...)):
    contents = await csv_file.read()
    df = pd.read_csv(io.BytesIO(contents), dtype=str)
    phone_list = []
    cols_map = {c.lower(): c for c in df.columns}
    
    has_cc = 'country_code' in cols_map or 'cc' in cols_map
    has_phone = 'phone' in cols_map or 'number' in cols_map
    
    if has_cc and has_phone:
        cc_col = cols_map.get('country_code') or cols_map.get('cc')
        ph_col = cols_map.get('phone') or cols_map.get('number')
        for _, row in df.iterrows():
            cc = str(row[cc_col]).strip() if pd.notna(row[cc_col]) else ""
            ph = str(row[ph_col]).strip() if pd.notna(row[ph_col]) else ""
            if ph and ph.lower() != 'nan':
                cc = cc.replace('.0', '').replace('+', '')
                ph = ph.replace('.0', '').replace('+', '')
                phone_list.append(f"+{cc}{ph}")
    else:
        target_col = df.columns[0]
        for n in df[target_col].astype(str).tolist():
            clean_n = n.strip().replace('.0', '')
            if clean_n and clean_n != 'nan':
                if not clean_n.startswith('+'): clean_n = '+' + clean_n
                phone_list.append(clean_n)

    unique_list = list(dict.fromkeys(phone_list)) # Preserves order
    return {"status": "success", "count": len(unique_list), "numbers": unique_list[:500]} # Limit to first 500 for UI performance

@app.get("/logout")
async def logout():
    global bridge_process, sending_status
    logger.info("🚪 Logging out and clearing session...")
    try:
        # 1. Full Reset of All Stats and Logs
        sending_status.update({
            "is_running": False,
            "current_index": 0,
            "total": 0,
            "success": 0,
            "failed": 0,
            "logs": ["✨ Session cleared. Ready for new connection."],
            "step": "logout_reset",
            "qr_code": None,
            "connected_user": None
        })
        
        # 2. Kill specifically Node
        subprocess.run("taskkill /F /IM node.exe /T", shell=True, capture_output=True)
        if bridge_process:
            try: bridge_process.kill()
            except: pass
            bridge_process = None
        
        # 3. Wipe session folder with retries
        time.sleep(5) 
        if os.path.exists(SESSION_DIR):
            def remove_readonly(func, path, excinfo):
                import stat
                os.chmod(path, stat.S_IWRITE)
                func(path)
                
            for i in range(5):
                try:
                    shutil.rmtree(SESSION_DIR, onerror=remove_readonly)
                    logger.info("✅ Session folder wiped.")
                    break
                except:
                    time.sleep(2)
            
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/force-kill")
async def force_kill():
    global sending_status, bridge_process
    sending_status["is_running"] = False
    subprocess.run("taskkill /F /IM node.exe /T", shell=True)
    if bridge_process:
        bridge_process.terminate()
        bridge_process = None
    return {"status": "success"}

@app.get("/stop-task")
async def stop_task():
    global sending_status
    sending_status["is_running"] = False
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    start_bridge()
    uvicorn.run(app, host="0.0.0.0", port=8000)
