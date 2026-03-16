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
import re
import pdfplumber
import openpyxl

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
SESSION_DIR = os.path.abspath("SESSIONS")

def ensure_dirs():
    for d in [UPLOAD_DIR, BRIDGE_DIR, SESSION_DIR]:
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

def bulk_send_task(numbers: List[str], message: str, image_path: str, delay: int, btn_text: str = "", btn_url: str = ""):
    global sending_status
    sending_status["is_running"] = True
    sending_status["total"] = len(numbers)
    sending_status["success"] = 0
    sending_status["failed"] = 0
    sending_status["current_index"] = 0
    sending_status["last_failed_info"] = None # Reset on start
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
            
            # Anti-spam measure: Append random invisible (zero-width) characters
            invisible_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF', '\u200E', '\u200F']
            unique_padding = "".join(random.choices(invisible_chars, k=random.randint(5, 12)))
            unique_message = message
            
            # Append CTA if present
            if btn_text or btn_url:
                cta_part = f"\n\n🔗 *{btn_text or 'Click Here'}*\n{btn_url}"
                unique_message += cta_part

            unique_message += "\n" + unique_padding
            
            payload = {
                "phone": clean_phone,
                "message": unique_message,
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
            error_msg = str(e)
            fail_info = f"FAILED: Row {i+1} | {phone} | {error_msg}"
            sending_status["last_failed_info"] = {
                "row": i + 1,
                "phone": phone,
                "error": error_msg
            }
            sending_status["logs"].append(f"❌ {fail_info}")
            sending_status["is_running"] = False # STOP IMMEDIATELY
            sending_status["step"] = "stopped_on_error"
            break

        
        if i < len(numbers) - 1:
            # Smart Pause: every 10 messages, take a longer break
            if (i + 1) % 10 == 0:
                smart_wait = random.randint(60, 180) # 1 to 3 minutes
                sending_status["logs"].append(f"🛌 Taking a Smart Pause for {smart_wait}s to stay stealthy...")
                time.sleep(smart_wait)
            else:
                # Normal variation
                wait = delay + random.randint(-5, 10) # More variation: -5s to +10s
                time.sleep(max(5, wait))

    sending_status["step"] = "finished"
    sending_status["logs"].append("🏁 Bulk send completed!")
    sending_status["is_running"] = False

    sending_status["is_running"] = False

def extract_phone_numbers(df: pd.DataFrame) -> List[str]:
    """Helper to find phone numbers in a dataframe"""
    phone_list = []
    cols_map = {c.lower(): c for c in df.columns}
    
    # Check for CC + Phone columns
    has_cc = 'country_code' in cols_map or 'cc' in cols_map
    has_phone = 'phone' in cols_map or 'number' in cols_map
    
    if has_cc and has_phone:
        cc_col = cols_map.get('country_code') or cols_map.get('cc')
        ph_col = cols_map.get('phone') or cols_map.get('number')
        for _, row in df.iterrows():
            cc = str(row[cc_col]).strip().split('.')[0] if pd.notna(row[cc_col]) else ""
            ph = str(row[ph_col]).strip().split('.')[0] if pd.notna(row[ph_col]) else ""
            if not ph or ph.lower() == 'nan': continue
            cc = cc.replace('+', '')
            ph = ph.replace('+', '')
            phone_list.append(f"+{cc}{ph}")
    else:
        # Scan all columns for things that look like numbers
        for col in df.columns:
            for val in df[col].astype(str):
                clean = re.sub(r'[^0-9+]', '', val)
                if len(clean) >= 10: # Basic length check
                    if not clean.startswith('+'): clean = '+' + clean
                    phone_list.append(clean)
    return phone_list

@app.post("/start-bulk")
async def start_bulk(
    background_tasks: BackgroundTasks,
    numbers_list: str = Form(None), # Direct JSON list or string
    gsheet_url: str = Form(""),
    message: str = Form(...),
    delay: int = Form(20),
    btn_text: str = Form(""),
    btn_url: str = Form(""),
    image: UploadFile = File(None),
    file_source: UploadFile = File(None)
):
    final_list = []

    # 1. Handle Direct List (if provided by UI after parsing)
    if numbers_list:
        try:
            import json
            final_list = json.loads(numbers_list)
        except: pass

    # 2. Handle GSheet
    if gsheet_url and not final_list:
        try:
            # Convert /edit to /export?format=csv
            if "/edit" in gsheet_url:
                export_url = gsheet_url.split("/edit")[0] + "/export?format=csv"
                if "gid=" in gsheet_url:
                    gid = gsheet_url.split("gid=")[1].split("&")[0]
                    export_url += f"&gid={gid}"
                resp = requests.get(export_url, timeout=10)
                if resp.status_code == 200:
                    df = pd.read_csv(io.BytesIO(resp.content), dtype=str)
                    final_list.extend(extract_phone_numbers(df))
        except Exception as e:
            logger.error(f"GSheet error: {e}")

    # 3. Handle Uploaded File
    if file_source and not final_list:
        filename = file_source.filename.lower()
        contents = await file_source.read()
        
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents), dtype=str)
            final_list.extend(extract_phone_numbers(df))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(contents), dtype=str)
            final_list.extend(extract_phone_numbers(df))
        elif filename.endswith(".pdf"):
            with pdfplumber.open(io.BytesIO(contents)) as pdf:
                full_text = ""
                for page in pdf.pages:
                    full_text += page.extract_text() or ""
                # Regex for phone numbers (basic international)
                found = re.findall(r'\+?\d{10,15}', full_text)
                final_list.extend(found)

    # Sanitize and unique
    cleaned = []
    seen = set()
    for p in final_list:
        p = p.replace(" ", "").replace("-", "")
        if not p.startswith('+'): p = '+' + p
        if p not in seen and len(p) > 10:
            seen.add(p)
            cleaned.append(p)
    
    image_path = ""
    if image and image.filename:
        filename = f"{uuid.uuid4()}_{image.filename}"
        image_path = os.path.join(UPLOAD_DIR, filename)
        with open(image_path, "wb") as f:
            f.write(await image.read())

    background_tasks.add_task(bulk_send_task, cleaned, message, image_path, delay, btn_text, btn_url)
    return {"status": "started", "total": len(cleaned)}

@app.post("/parse-source")
async def parse_source(
    file_source: UploadFile = File(None),
    gsheet_url: str = Form("")
):
    phone_list = []
    
    if gsheet_url:
        try:
            if "/edit" in gsheet_url:
                export_url = gsheet_url.split("/edit")[0] + "/export?format=csv"
                if "gid=" in gsheet_url:
                    gid = gsheet_url.split("gid=")[1].split("&")[0]
                    export_url += f"&gid={gid}"
                resp = requests.get(export_url, timeout=10)
                if resp.status_code == 200:
                    df = pd.read_csv(io.BytesIO(resp.content), dtype=str)
                    phone_list.extend(extract_phone_numbers(df))
        except: pass

    if file_source:
        filename = file_source.filename.lower()
        contents = await file_source.read()
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents), dtype=str)
            phone_list.extend(extract_phone_numbers(df))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(contents), dtype=str)
            phone_list.extend(extract_phone_numbers(df))
        elif filename.endswith(".pdf"):
            with pdfplumber.open(io.BytesIO(contents)) as pdf:
                full_text = ""
                for page in pdf.pages:
                    full_text += page.extract_text() or ""
                found = re.findall(r'\+?\d{10,15}', full_text)
                phone_list.extend(found)

    seen = set()
    unique = []
    for p in phone_list:
        p = p.replace(" ", "").replace("-", "").replace(".0", "")
        if not p.startswith('+'): p = '+' + p
        if p not in seen and len(p) > 10:
            seen.add(p)
            unique.append(p)

    return {"status": "success", "count": len(unique), "numbers": unique[:500]}

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
    ensure_dirs()
    start_bridge()
    uvicorn.run(app, host="0.0.0.0", port=8000)
