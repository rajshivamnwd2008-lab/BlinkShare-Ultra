import os
import socket
import threading
import time
from datetime import datetime
import pyperclip
from flask import Flask, jsonify, request, render_template_string
from werkzeug.utils import secure_filename
import random
import string

# Configuration
HOST = "0.0.0.0"
PORT = 5000
CLIPBOARD_CHECK_INTERVAL = 2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "blinkshare_files")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB Limit

# State Variables for Dynamic Security
state_lock = threading.Lock()
clipboard_text = ""
clipboard_updated_at = None
clipboard_history = []
MAX_HISTORY = 50

# App Security State
current_password = "1234"  
file_transfer_count = 0  
MAX_TRANSFERS_BEFORE_RESET = 3  
device_authenticated = False  

def generate_new_password():
    return "".join(random.choices(string.digits, k=4))

def get_local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        local_ip = sock.getsockname()[0]
    except OSError:
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            local_ip = "127.0.0.1"
    finally:
        sock.close()
    return local_ip

# HTML Interface with Dynamic Multi-Device Connection Protocol
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="hi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BlinkShare Dynamic Link</title>
    <style>
        * { box-sizing: border-box; transition: all 0.3s ease; }
        body { 
            margin: 0; font-family: 'Segoe UI', Roboto, sans-serif; 
            background: radial-gradient(circle at top, #1e1b4b, #0f172a); 
            color: #f1f5f9; min-height: 100vh; padding: 15px;
            display: flex; align-items: center; justify-content: center;
        }
        .container { width: min(480px, 100%); margin: 0 auto; }
        .card { 
            background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px);
            border: 1px solid rgba(71, 85, 105, 0.4); border-radius: 20px; padding: 25px; 
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
        }
        .logo { display: flex; align-items: center; justify-content: center; width: 60px; height: 60px; border-radius: 18px; background: linear-gradient(135deg, #06b6d4, #3b82f6); font-size: 28px; margin: 0 auto 15px; box-shadow: 0 0 20px rgba(59, 130, 246, 0.5); }
        h2 { text-align: center; margin: 0 0 10px; font-size: 24px; background: linear-gradient(to right, #38bdf8, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .alert-box { background: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; color: #fca5a5; padding: 10px; border-radius: 10px; text-align: center; margin-bottom: 15px; font-size: 14px; }
        input[type="text"], textarea { width: 100%; background: rgba(15, 23, 42, 0.6); color: #f8fafc; border: 1px solid #334155; border-radius: 12px; padding: 12px; font-size: 15px; outline: none; margin-bottom: 15px; }
        button { width: 100%; background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white; border: 0; padding: 12px; border-radius: 12px; cursor: pointer; font-weight: 600; font-size: 14px; }
        button:hover { transform: translateY(-1px); box-shadow: 0 6px 15px rgba(37, 99, 235, 0.3); }
        .hidden { display: none; }
        .file-box { border: 2px dashed #475569; padding: 15px; border-radius: 12px; text-align: center; background: rgba(15, 23, 42, 0.4); }
        .badge { background: #3b82f6; padding: 3px 8px; border-radius: 20px; font-size: 12px; float: right; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Step 1: Laptop Verification Window -->
        <div id="authCard" class="card">
            <div class="logo">🔑</div>
            <h2>Device Connection Password</h2>
            <p style="text-align:center; font-size:13px; color:#94a3b8; margin-top:0;">Mobile screen par dikh raha password yahan dalein taaki connection pakka ho sake.</p>
            <input type="text" id="passInput" placeholder="4 Digits ka Password bharein">
            <button onclick="verifyConnection()">Laptop Se Connect Karein</button>
        </div>

        <!-- Step 2: Main Working Dashboard -->
        <div id="dashboardCard" class="card hidden">
            <div class="logo">⚡</div>
            <h2>BlinkShare Ultra <span id="transferBadge" class="badge">0/3 Files</span></h2>
            
            <div id="passChangeAlert" class="alert-box hidden">⚠️ Security Alert: 3 File transfers complete! Password badal gaya hai. Naya password dalein.</div>

            <h3 style="font-size:14px; color:#94a3b8; margin:15px 0 8px;">📱 Laptop Par Text Bhejein</h3>
            <textarea id="sendText" placeholder="Yahan kuch bhi likhein..."></textarea>
            <button onclick="sendText()" style="margin-bottom:20px;">🚀 Text Bhejein</button>

            <h3 style="font-size:14px; color:#94a3b8; margin:0 0 8px;">📁 Photo / File Laptop Par Upload Karein</h3>
            <div class="file-box">
                <input type="file" id="fileInput" style="width: 100%; color: #94a3b8;">
                <button onclick="uploadFile()" style="background: linear-gradient(135deg, #10b981, #059669); margin-top: 10px;">📤 File Upload Karein</button>
            </div>
        </div>
    </div>

    <script>
        async function verifyConnection() {
            let pass = document.getElementById('passInput').value;
            let res = await fetch('/api/verify', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ password: pass })
            });
            let data = await res.json();
            if(data.status === 'success') {
                document.getElementById('authCard').classList.add('hidden');
                document.getElementById('dashboardCard').classList.remove('hidden');
                updateStatus();
            } else {
                alert('Galat Password! Kripya sahi password bharein.');
            }
        }

        async function updateStatus() {
            let res = await fetch('/api/check-status');
            let data = await res.json();
            
            if(data.require_reauth) {
                document.getElementById('dashboardCard').classList.add('hidden');
                document.getElementById('authCard').classList.remove('hidden');
                document.getElementById('passInput').value = "";
                alert('Security Rule: 3 Files transfer ho chuki hain. Laptop screen par naya password dekhein!');
                return;
            }
            
            document.getElementById('transferBadge').innerText = data.count + "/3 Files";
            setTimeout(updateStatus, 3000);
        }

        async function sendText() {
            let val = document.getElementById('sendText').value;
            if(!val.trim()) return;
            let res = await fetch('/api/send-text', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ text: val })
            });
            let data = await res.json();
            if(data.status === 'success') {
                alert('Text successfully bhej diya gaya!');
                document.getElementById('sendText').value = "";
            }
        }

        async function uploadFile() {
            let fileInput = document.getElementById('fileInput');
            if(fileInput.files.length === 0) return;
            
            let formData = new FormData();
            formData.append('file', fileInput.files[0]);
            
            let res = await fetch('/api/upload-file', { method: 'POST', body: formData });
            let data = await res.json();
            if(data.status === 'success') {
                alert('🎉 File successfully laptop par aa gayi!');
                fileInput.value = "";
            } else {
                alert('Upload fail ho gaya!');
            }
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

@app.route("/api/verify", methods=["POST"])
def verify():
    global device_authenticated
    data = request.get_json() or {}
    if data.get("password") == current_password:
        device_authenticated = True
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 401

@app.route("/api/check-status", methods=["GET"])
def check_status():
    return jsonify({
        "count": file_transfer_count,
        "require_reauth": not device_authenticated
    })

def trigger_password_reset():
    global current_password, file_transfer_count, device_authenticated
    file_transfer_count += 1
    if file_transfer_count >= MAX_TRANSFERS_BEFORE_RESET:
        current_password = generate_new_password()
        file_transfer_count = 0
        device_authenticated = False  
        print("\n" + "🛑"*20)
        print(f" ⚠️ SECURITY ALERT: 3 File transfers complete!")
        print(f" 🔑 Aapka naya connection password hai: {current_password}")
        print("🛑"*20 + "\n")

@app.route("/api/send-text", methods=["POST"])
def send_text():
    if not device_authenticated:
        return jsonify({"status": "locked"}), 403
    data = request.get_json() or {}
    text = data.get("text", "")
    if text.strip():
        pyperclip.copy(text)
        trigger_password_reset()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route("/api/upload-file", methods=["POST"])
def upload_file():
    if not device_authenticated:
        return jsonify({"status": "locked"}), 403
    if 'file' not in request.files:
        return jsonify({"status": "error"}), 400
    file = request.files['file']
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_DIR, filename))
        trigger_password_reset()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

if __name__ == "__main__":
    local_ip = get_local_ip()
    print("\n" + "="*50)
    print(f" 🚀 BlinkShare Ultra Secure Active!")
    print(f" 🔑 Aapka pehla connection password hai: {current_password}")
    print(f" 📱 Mobile me yeh link kholein: http://{local_ip}:{PORT}")
    print("="*50 + "\n")
    
    app.run(host=HOST, port=PORT, debug=False, threaded=True)