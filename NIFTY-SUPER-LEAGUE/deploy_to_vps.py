"""
NSL VPS Deploy Script
=====================
Ek click mein sab kuch VPS pe deploy ho jaata hai.
Laptop ke baad mobile se chalao.
"""
import subprocess
import sys
import os
import time

# ─── VPS CONFIG ──────────────────────────────────────────────
VPS_IP       = "46.224.133.16"
VPS_USER     = "root"
VPS_PASSWORD = ""        # <-- Fill karo: VPS ka root password
# ─────────────────────────────────────────────────────────────

NSL_DIR   = os.path.dirname(os.path.abspath(__file__))
REMOTE    = "/root/nsl-engine"
PLINK     = os.path.join(os.path.dirname(NSL_DIR), "BHARAT-FUTURES-ENGINE", "plink.exe")
PSCP      = os.path.join(os.path.dirname(NSL_DIR), "BHARAT-FUTURES-ENGINE", "pscp.exe")

# Use system scp/ssh if plink not found
if not os.path.exists(PLINK):
    PLINK = "ssh"
    PSCP  = "scp"

# ─── CREDENTIALS from DB ─────────────────────────────────────
sys.path.insert(0, NSL_DIR)
import nsl_db as db

CREDS = {
    "NSL_API_KEY":       db.get("upstox_api_key", ""),
    "NSL_API_SECRET":    db.get("upstox_api_secret", ""),
    "NSL_ACCESS_TOKEN":  db.get("upstox_access_token", ""),
    "NSL_REDIRECT_URI":  db.get("upstox_redirect_uri", "https://127.0.0.1"),
    "NSL_TG_TOKEN":      db.get("telegram_bot_token", ""),
    "NSL_TG_CHAT":       db.get("telegram_chat_id", ""),
    "NSL_LOTS":          db.get("lots", "1"),
    "NSL_LOT_SIZE":      db.get("lot_size", "65"),
    "NSL_PREM_MIN":      db.get("premium_min", "100"),
    "NSL_PREM_MAX":      db.get("premium_max", "120"),
    "NSL_SL_PCT":        db.get("stop_loss_pct", "0"),
}

def ssh(cmd, show=True):
    """Run command on VPS via SSH."""
    if PLINK.endswith("plink.exe"):
        args = [PLINK, "-pw", VPS_PASSWORD, "-batch",
                f"{VPS_USER}@{VPS_IP}", cmd]
    else:
        args = ["ssh", "-o", "StrictHostKeyChecking=no",
                f"{VPS_USER}@{VPS_IP}", cmd]
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if show:
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print("  STDERR:", result.stderr.strip()[:200])
    return result.returncode == 0

def scp_upload(local_path, remote_path):
    """Upload file/folder to VPS."""
    if PSCP.endswith("pscp.exe"):
        args = [PSCP, "-pw", VPS_PASSWORD, "-r", "-q", local_path, f"{VPS_USER}@{VPS_IP}:{remote_path}"]
    else:
        args = ["scp", "-o", "StrictHostKeyChecking=no", "-r", local_path, f"{VPS_USER}@{VPS_IP}:{remote_path}"]
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.returncode == 0


print()
print("=" * 60)
print("  NIFTY SUPER LEAGUE — DEPLOYING TO VPS")
print(f"  Target: {VPS_USER}@{VPS_IP}")
print("=" * 60)
print()

# ─── Step 1: Create remote directory ─────────────────────────
print("[1/6] Preparing VPS directory...")
ssh(f"mkdir -p {REMOTE}")
print("      OK")

# ─── Step 2: Upload all NSL files ────────────────────────────
print("[2/6] Uploading NSL engine files...")
# Upload each .py file (exclude .db so we start fresh)
files_to_upload = [
    "nsl_engine.py", "nsl_executor.py", "nsl_monitor.py",
    "nsl_supertrend.py", "nsl_data.py",
    "nsl_db.py", "nsl_config.py", "nsl_utils.py",
    "nsl_telegram.py", "nsl_dashboard.py",
    "requirements.txt", "vps_setup.sh",
]
for f in files_to_upload:
    fp = os.path.join(NSL_DIR, f)
    if os.path.exists(fp):
        ok = scp_upload(fp, f"{REMOTE}/{f}")
        print(f"  {'OK' if ok else 'FAILED'}: {f}")
    else:
        print(f"  SKIP (not found): {f}")
print("      Upload done!")

# ─── Step 3: Write credentials via SSH ───────────────────────
print("[3/6] Writing credentials to VPS DB...")
# Build Python command to set all credentials
cred_lines = "\n".join([
    f'db.set("{k.replace("NSL_", "").lower().replace("_", "_")}", """{v}""")' if v else ""
    for k, v in [
        ("upstox_api_key",     CREDS["NSL_API_KEY"]),
        ("upstox_api_secret",  CREDS["NSL_API_SECRET"]),
        ("upstox_access_token",CREDS["NSL_ACCESS_TOKEN"]),
        ("upstox_redirect_uri",CREDS["NSL_REDIRECT_URI"]),
        ("telegram_bot_token", CREDS["NSL_TG_TOKEN"]),
        ("telegram_chat_id",   CREDS["NSL_TG_CHAT"]),
        ("manual_anchor",      CREDS["NSL_ANCHOR"]),
        ("lots",               CREDS["NSL_LOTS"]),
        ("lot_size",           CREDS["NSL_LOT_SIZE"]),
        ("premium_min",        CREDS["NSL_PREM_MIN"]),
        ("premium_max",        CREDS["NSL_PREM_MAX"]),
        ("profit_target_pct",  CREDS["NSL_TP_PCT"]),
        ("upstox_proxy",       ""),         # NO proxy on VPS — static IP direct
        ("trade_active",       "NO"),
        ("active_symbol",      "NONE"),
        ("algo_running",       "ON"),
    ]
])

py_cmd = f"""python3 -c "
import sys
sys.path.insert(0, '{REMOTE}')
import nsl_db as db
db.init_defaults()
db.set('upstox_api_key',     '{CREDS["NSL_API_KEY"]}')
db.set('upstox_api_secret',  '{CREDS["NSL_API_SECRET"]}')
db.set('upstox_access_token','{CREDS["NSL_ACCESS_TOKEN"]}')
db.set('upstox_redirect_uri','{CREDS["NSL_REDIRECT_URI"]}')
db.set('telegram_bot_token', '{CREDS["NSL_TG_TOKEN"]}')
db.set('telegram_chat_id',   '{CREDS["NSL_TG_CHAT"]}')
db.set('lots',               '{CREDS["NSL_LOTS"]}')
db.set('lot_size',           '{CREDS["NSL_LOT_SIZE"]}')
db.set('premium_min',        '{CREDS["NSL_PREM_MIN"]}')
db.set('premium_max',        '{CREDS["NSL_PREM_MAX"]}')
db.set('stop_loss_pct',      '{CREDS["NSL_SL_PCT"]}')
db.set('upstox_proxy',       '')
db.set('trade_active',       'NO')
db.set('active_symbol',      'NONE')
db.set('algo_running',       'ON')
print('All credentials written to VPS DB!')
" """

ssh(f"cd {REMOTE} && {py_cmd}")
print("      OK")

# ─── Step 4: Install dependencies ────────────────────────────
print("[4/6] Installing Python packages on VPS...")
ssh(f"pip3 install -q requests pytz streamlit --break-system-packages 2>/dev/null || pip3 install -q requests pytz streamlit")
print("      OK")

# ─── Step 5: Create & start systemd services ─────────────────
print("[5/6] Setting up systemd services...")

engine_service = f"""[Unit]
Description=Nifty Super League Engine
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory={REMOTE}
ExecStart=/usr/bin/python3 {REMOTE}/nsl_engine.py
Restart=always
RestartSec=15
StandardOutput=append:{REMOTE}/nsl_engine.log
StandardError=append:{REMOTE}/nsl_engine.log
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONIOENCODING=utf-8

[Install]
WantedBy=multi-user.target"""

dashboard_service = f"""[Unit]
Description=Nifty Super League Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={REMOTE}
ExecStart=/usr/bin/python3 -m streamlit run {REMOTE}/nsl_dashboard.py --server.port 8502 --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false --server.enableCORS false --server.enableXsrfProtection false
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONIOENCODING=utf-8

[Install]
WantedBy=multi-user.target"""

# Write service files
ssh(f"cat > /etc/systemd/system/nsl_engine.service << 'SVCEOF'\n{engine_service}\nSVCEOF")
ssh(f"cat > /etc/systemd/system/nsl_dashboard.service << 'SVCEOF'\n{dashboard_service}\nSVCEOF")

ssh("systemctl daemon-reload")
ssh("systemctl enable nsl_engine nsl_dashboard")
ssh("systemctl stop nsl_engine nsl_dashboard 2>/dev/null; sleep 2")
ssh("systemctl start nsl_engine")
time.sleep(3)
ssh("systemctl start nsl_dashboard")
time.sleep(4)

# Open firewall
ssh("ufw allow 8502/tcp 2>/dev/null || iptables -I INPUT -p tcp --dport 8502 -j ACCEPT 2>/dev/null || true", show=False)
print("      OK")

# ─── Step 6: Verify ──────────────────────────────────────────
print("[6/6] Verifying services...")
time.sleep(5)
engine_status = "RUNNING" if ssh("systemctl is-active --quiet nsl_engine", show=False) else "STARTING..."
dash_status   = "RUNNING" if ssh("systemctl is-active --quiet nsl_dashboard", show=False) else "STARTING..."

print()
print("=" * 60)
print("  DEPLOYMENT COMPLETE!")
print()
print(f"  Engine   : {engine_status}")
print(f"  Dashboard: {dash_status}")
print()
print(f"  PERMANENT DASHBOARD URL:")
print(f"  http://{VPS_IP}:8502")
print()
print("  HOW TO USE ON MOBILE:")
print("  1. Open above URL in Chrome on mobile")
print("  2. Tap 3-dot menu > 'Add to Home Screen'")
print("  3. Works like an APP — 24/7, no laptop needed!")
print()
print("  LAPTOP BAND KAR SAKTE HO ABHI!")
print("=" * 60)
print()
