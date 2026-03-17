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
    "total": 0,
    "success": 0,
    "failed": 0,
    "current_index": 0,
    "current_phone": "",
    "logs": [],
    "connected_user": None,
    "qr_code": None,
    "step": "idle",
    "last_failed_info": None,
    "campaign_report": [] # Store results for CSV download
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

def parse_spintax(text: str) -> str:
    """Randomly picks one variation. Only matches if a '|' is present to avoid {{Tags}}"""
    while True:
        # Match {word1|word2} but ignore {tag}
        match = re.search(r'\{([^{}|]*\|[^{}]*)\}', text)
        if not match:
            break
        choices = match.group(1).split('|')
        text = text.replace(match.group(0), random.choice(choices), 1)
    return text

def apply_variables(text: str, vars_dict: dict) -> str:
    """Replaces {{Name}} with the value from vars_dict. CASE INSENSITIVE."""
    for key, val in vars_dict.items():
        # Match {{Name}} or {{name}}
        pattern = re.compile(re.escape("{{" + str(key) + "}}"), re.IGNORECASE)
        text = pattern.sub(str(val), text)
    return text

def bulk_send_task(items: List[dict], message: str, image_path: str, delay: int, 
                   btn_text: str = "", btn_url: str = "", 
                   use_spintax: bool = False, use_safe_start: bool = False):
    global sending_status
    sending_status["is_running"] = True
    sending_status["total"] = len(items)
    sending_status["success"] = 0
    sending_status["failed"] = 0
    sending_status["current_index"] = 0
    sending_status["last_failed_info"] = None 
    sending_status["campaign_report"] = [] 
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

    for i, item in enumerate(items):
        if not sending_status["is_running"]: break
        
        phone = item["phone"]
        vars = item.get("vars", {})
        
        sending_status["current_index"] = i + 1
        sending_status["current_phone"] = phone
        clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")
        
        # Initialize fresh message and URL for this item
        final_msg = message
        final_btn_url = btn_url
        
        # 1. Personalization (Run FIRST)
        final_msg = apply_variables(final_msg, vars)
        
        # 2. Spintax (Run SECOND)
        if use_spintax:
            final_msg = parse_spintax(final_msg)
        
        # 3. Dynamic Button URLs (can also have vars)
        final_btn_url = apply_variables(final_btn_url, vars)
        
        try:
            sending_status["logs"].append(f"📤 [{i+1}/{len(items)}] Sending to {phone}...")
            
            # Simulated Typing
            requests.get(f"http://localhost:3001/typing?phone={clean_phone}&duration=2", timeout=5)
            
            payload = {
                "phone": clean_phone,
                "message": final_msg,
                "image": image_path
            }
            if btn_text and final_btn_url:
                payload["cta_text"] = btn_text
                payload["cta_url"] = final_btn_url

            resp = requests.post("http://localhost:3001/send", json=payload, timeout=30).json()
            
            if resp.get("status") == "success":
                sending_status["success"] += 1
                sending_status["logs"].append(f"✅ Sent successfully to {phone}")
                sending_status["campaign_report"].append({
                    "phone": phone, "status": "Success", "error": "", "row": i+1, **vars
                })
            else:
                raise Exception(resp.get("error", "Unknown error"))
                
        except Exception as e:
            err_msg = str(e)
            sending_status["failed"] += 1
            sending_status["logs"].append(f"❌ Failed for {phone}: {err_msg}")
            sending_status["last_failed_info"] = {"row": i+1, "phone": phone, "error": err_msg}
            sending_status["campaign_report"].append({
                "phone": phone, "status": "Failed", "error": err_msg, "row": i+1, **vars
            })
            sending_status["step"] = "stopped_on_error"
            sending_status["logs"].append("🚨 Engine STOPPED due to failure.")
            sending_status["is_running"] = False
            break

        if i < len(items) - 1:
            # 4. Safe Start (Warmup Mode)
            # Starts with 3x delay and slowly reduces to 1x over first 10 messages
            current_delay = delay
            if use_safe_start and i < 10:
                multiplier = 3.0 - (i * 0.2) # 3.0, 2.8, 2.6 ... 1.2, 1.0
                current_delay = int(delay * max(1.0, multiplier))
                sending_status["logs"].append(f"🌬️ Safe-Start in effect: Delay is {current_delay}s")

            # Smart Pause
            if (i + 1) % 10 == 0:
                smart_wait = random.randint(60, 180) 
                sending_status["logs"].append(f"🛌 Smart Pause for {smart_wait}s...")
                time.sleep(smart_wait)
            else:
                wait = current_delay + random.randint(-2, 5) 
                time.sleep(max(3, wait))

    if sending_status["step"] != "stopped_on_error":
        sending_status["step"] = "finished"
        sending_status["logs"].append("🏁 Bulk send completed!")
    
    sending_status["is_running"] = False

def extract_phone_numbers(df: pd.DataFrame) -> List[dict]:
    """Helper to return phone + all other columns as variables"""
    results = []
    cols_map = {c.lower(): c for c in df.columns}
    
    cc_col = cols_map.get('country_code') or cols_map.get('cc')
    ph_col = cols_map.get('phone') or cols_map.get('number')
    
    for idx, row in df.iterrows():
        phone = ""
        # 1. Detection
        if cc_col and ph_col:
            cc = str(row[cc_col]).strip().split('.')[0] if pd.notna(row[cc_col]) else ""
            ph = str(row[ph_col]).strip().split('.')[0] if pd.notna(row[ph_col]) else ""
            cc = cc.replace('+', '')
            ph = ph.replace('+', '')
            phone = f"+{cc}{ph}"
        else:
            # Use first column that looks like a number
            for col in df.columns:
                val = str(row[col])
                clean = re.sub(r'[^0-9+]', '', val)
                if len(clean) >= 10:
                    phone = clean if clean.startswith('+') else '+' + clean
                    break
        
        if phone:
            # Map all row data into variables
            vars = {str(k): str(v) for k, v in row.items() if pd.notna(v)}
            results.append({"phone": phone, "vars": vars})
            
    return results

@app.post("/start-bulk")
async def start_bulk(
    background_tasks: BackgroundTasks,
    items_json: str = Form(None), 
    gsheet_url: str = Form(""),
    message: str = Form(...),
    delay: int = Form(20),
    btn_text: str = Form(""),
    btn_url: str = Form(""),
    use_spintax: bool = Form(False),
    use_safe_start: bool = Form(False),
    image: UploadFile = File(None),
    file_source: UploadFile = File(None)
):
    final_items = []

    if items_json:
        try:
            import json
            final_items = json.loads(items_json)
        except: pass

    if gsheet_url and not final_items:
        try:
            if "/edit" in gsheet_url:
                export_url = gsheet_url.split("/edit")[0] + "/export?format=csv"
                if "gid=" in gsheet_url:
                    gid = gsheet_url.split("gid=")[1].split("&")[0]
                    export_url += f"&gid={gid}"
                resp = requests.get(export_url, timeout=10)
                if resp.status_code == 200:
                    df = pd.read_csv(io.BytesIO(resp.content), dtype=str)
                    final_items.extend(extract_phone_numbers(df))
        except: pass

    if file_source and not final_items:
        filename = file_source.filename.lower()
        contents = await file_source.read()
        
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents), dtype=str)
            final_items.extend(extract_phone_numbers(df))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(contents), dtype=str)
            final_items.extend(extract_phone_numbers(df))

    image_path = ""
    if image and image.filename:
        filename = f"{uuid.uuid4()}_{image.filename}"
        image_path = os.path.join(UPLOAD_DIR, filename)
        with open(image_path, "wb") as f:
            f.write(await image.read())

    background_tasks.add_task(bulk_send_task, final_items, message, image_path, delay, btn_text, btn_url, use_spintax, use_safe_start)
    return {"status": "started", "total": len(final_items)}

@app.post("/parse-source")
async def parse_source(
    file_source: UploadFile = File(None),
    gsheet_url: str = Form("")
):
    items = []
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
                    items.extend(extract_phone_numbers(df))
        except: pass

    if file_source:
        filename = file_source.filename.lower()
        contents = await file_source.read()
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents), dtype=str)
            items.extend(extract_phone_numbers(df))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(contents), dtype=str)
            items.extend(extract_phone_numbers(df))

    return {"status": "success", "count": len(items), "items": items[:500]}

@app.get("/download-report")
async def download_report():
    if not sending_status["campaign_report"]:
        return {"error": "No report available"}
    
    df = pd.DataFrame(sending_status["campaign_report"])
    path = os.path.join(UPLOAD_DIR, "campaign_report.csv")
    df.to_csv(path, index=False)
    return FileResponse(path, filename="Campaign_Report.csv")

@app.get("/download-template")
async def download_template(format: str = "xlsx"):
    data = {
        "Country_Code": ["91", "44"],
        "Phone": ["9876543210", "7123456789"],
        "Name": ["Rahul", "John"],
        "City": ["Mumbai", "London"],
        "Notes": ["Order 123", "Interested"]
    }
    df = pd.DataFrame(data)
    
    if format == "csv":
        path = os.path.join(UPLOAD_DIR, "sample_template.csv")
        df.to_csv(path, index=False)
        return FileResponse(path, filename="WA_Bulk_Template.csv", media_type="text/csv")
    else:
        path = os.path.join(UPLOAD_DIR, "sample_template.xlsx")
        df.to_excel(path, index=False, engine='openpyxl')
        return FileResponse(path, filename="WA_Bulk_Template.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

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
