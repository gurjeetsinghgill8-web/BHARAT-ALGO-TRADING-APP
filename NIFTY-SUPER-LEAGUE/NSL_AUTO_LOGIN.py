"""
NSL_AUTO_LOGIN.py — NIFTY SUPER LEAGUE
=======================================
Fully automatic daily token refresh using TOTP.
No browser interaction needed. Run this every morning.

How it works:
1. Reads credentials from secrets.toml automatically
2. Launches headless Chrome, enters phone + TOTP + PIN
3. Saves fresh token to secrets.toml and NSL DB
4. Sends Telegram confirmation
"""

import time, requests, urllib.parse, os, re, sys
import pyotp
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ── Paths ──────────────────────────────────────────────────────
THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.join(THIS_DIR, "..")
TOML_PATH  = os.path.join(PARENT_DIR, ".streamlit", "secrets.toml")

sys.path.insert(0, THIS_DIR)
import nsl_db as db

# ── Load all credentials ───────────────────────────────────────
def _read_toml():
    keys = {}
    if os.path.exists(TOML_PATH):
        with open(TOML_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#") and not line.startswith("["):
                    k, _, v = line.partition("=")
                    keys[k.strip().upper()] = v.strip().strip('"').strip("'")
    return keys

def run_auto_login():
    print("=" * 60)
    print("  NSL AUTO LOGIN — Refreshing Token")
    print("=" * 60)

    toml = _read_toml()
    API_KEY      = toml.get("UPSTOX_API_KEY", "")
    API_SECRET   = toml.get("UPSTOX_API_SECRET", "")
    REDIRECT_URI = toml.get("UPSTOX_REDIRECT_URI", "https://127.0.0.1")
    PHONE        = toml.get("UPSTOX_PHONE", "")
    PIN          = toml.get("UPSTOX_PIN", "")
    TOTP_SECRET  = toml.get("UPSTOX_TOTP_SECRET", "")

    # Validate
    missing = []
    if not API_KEY:     missing.append("UPSTOX_API_KEY")
    if not API_SECRET:  missing.append("UPSTOX_API_SECRET")
    if not PHONE:       missing.append("UPSTOX_PHONE")
    if not PIN:         missing.append("UPSTOX_PIN")
    if not TOTP_SECRET: missing.append("UPSTOX_TOTP_SECRET")

    if missing:
        print(f"\nMissing in secrets.toml: {missing}")
        print("Please add them and try again.")
        return False

    print(f"\nPhone  : {PHONE[:4]}****")
    print(f"API Key: {API_KEY[:8]}...")
    print(f"TOTP   : Will be auto-generated")
    print()

    # ── Launch Chrome ──────────────────────────────────────────
    print("[1/5] Starting Chrome browser...")
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,800")
    opts.add_argument("--disable-extensions")

    try:
        service = Service(ChromeDriverManager().install())
        driver  = webdriver.Chrome(service=service, options=opts)
        driver.set_page_load_timeout(30)
        print("[1/5] Chrome started OK")
    except Exception as e:
        print(f"[ERROR] Chrome failed to start: {e}")
        print("\nTrying alternative: manual code entry...")
        return _manual_fallback(API_KEY, API_SECRET, REDIRECT_URI)

    try:
        # Step 1: Navigate to auth URL
        params   = {"response_type": "code", "client_id": API_KEY, "redirect_uri": REDIRECT_URI}
        auth_url = "https://api.upstox.com/v2/login/authorization/dialog?" + urllib.parse.urlencode(params)
        print(f"[2/5] Opening Upstox login page...")
        driver.get(auth_url)
        time.sleep(3)

        wait = WebDriverWait(driver, 20)

        # Step 2: Enter phone number
        print(f"[2/5] Entering phone number...")
        phone_input = wait.until(EC.presence_of_element_located((By.ID, "mobileNum")))
        phone_input.clear()
        phone_input.send_keys(PHONE)
        driver.find_element(By.ID, "getOtp").click()
        time.sleep(2)

        # Step 3: Enter TOTP (auto-generated)
        print("[3/5] Generating and entering TOTP...")
        totp_code = pyotp.TOTP(TOTP_SECRET).now()
        print(f"       TOTP generated: {totp_code}")
        otp_input = wait.until(EC.presence_of_element_located((By.ID, "otpNum")))
        otp_input.clear()
        otp_input.send_keys(totp_code)
        driver.find_element(By.ID, "continueBtn").click()
        time.sleep(2)

        # Step 4: Enter PIN
        print("[4/5] Entering PIN...")
        pin_input = wait.until(EC.presence_of_element_located((By.ID, "pinCode")))
        pin_input.clear()
        pin_input.send_keys(PIN)
        time.sleep(1)

        # Wait for redirect with code
        print("[4/5] Waiting for redirect...")
        wait.until(EC.url_contains("code="))
        current_url = driver.current_url
        auth_code   = current_url.split("code=")[1].split("&")[0]
        print(f"[4/5] Auth code captured!")

    except Exception as e:
        print(f"[ERROR] Login flow failed: {e}")
        driver.quit()
        return _manual_fallback(API_KEY, API_SECRET, REDIRECT_URI)
    finally:
        try: driver.quit()
        except: pass

    # Step 5: Exchange code for token
    return _exchange_code(auth_code, API_KEY, API_SECRET, REDIRECT_URI)


def _exchange_code(code, api_key, api_secret, redirect_uri):
    print("[5/5] Fetching access token...")
    try:
        resp = requests.post(
            "https://api.upstox.com/v2/login/authorization/token",
            headers={"accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            data={"code": code, "client_id": api_key, "client_secret": api_secret,
                  "redirect_uri": redirect_uri, "grant_type": "authorization_code"},
            timeout=15
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token", "")
            if token:
                _save_token(token)
                print("\n" + "=" * 60)
                print("  SUCCESS! Token refreshed and saved.")
                print("  Start the engine: double-click START.bat")
                print("=" * 60)
                return True
            else:
                print(f"[ERROR] No token in response: {resp.text}")
        else:
            err = resp.json().get("errors", [{}])[0].get("message", "Unknown")
            print(f"[ERROR] {resp.status_code}: {err}")
    except Exception as e:
        print(f"[ERROR] Network error: {e}")
    return False


def _save_token(token):
    """Save token to NSL DB and secrets.toml"""
    # NSL DB
    db.set("upstox_access_token", token)
    print("    Saved to nsl_trader.db")

    # secrets.toml
    if os.path.exists(TOML_PATH):
        with open(TOML_PATH, "r") as f: content = f.read()
        new_line = f'UPSTOX_ACCESS_TOKEN = "{token}"'
        if re.search(r"(?im)^UPSTOX_ACCESS_TOKEN\s*=", content):
            content = re.sub(r"(?im)^UPSTOX_ACCESS_TOKEN\s*=.*$", new_line, content)
        else:
            content += f"\n{new_line}\n"
        with open(TOML_PATH, "w") as f: f.write(content)
        print("    Saved to secrets.toml")

    # Telegram notification
    try:
        tg_token = db.get("telegram_bot_token", "")
        tg_chat  = db.get("telegram_chat_id", "")
        if tg_token and tg_chat:
            requests.post(
                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                json={"chat_id": tg_chat, "text": "🔑 NSL Token Refreshed!\nUpstox token saved. Engine ready to start.", "parse_mode": "HTML"},
                timeout=8
            )
            print("    Telegram notified")
    except:
        pass


def _manual_fallback(api_key, api_secret, redirect_uri):
    """If Chrome fails, show URL and ask for code"""
    params   = {"response_type": "code", "client_id": api_key, "redirect_uri": redirect_uri}
    auth_url = "https://api.upstox.com/v2/login/authorization/dialog?" + urllib.parse.urlencode(params)
    print("\nChrome unavailable. Manual login:")
    print(f"\n  Open this URL in browser:\n  {auth_url}\n")
    print(f"  Login -> browser goes to {redirect_uri}/?code=XXXXXX")
    print("  Copy the code from URL bar\n")
    code = input("  Paste code here: ").strip()
    if code:
        return _exchange_code(code, api_key, api_secret, redirect_uri)
    return False


if __name__ == "__main__":
    db.load_shared_secrets()
    run_auto_login()
