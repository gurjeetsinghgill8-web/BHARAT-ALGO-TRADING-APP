import time
import requests
import urllib.parse
import os
import pyotp
import db
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def run_auto_login():
    print("="*60)
    # 0. Initialize variables
    API_KEY, API_SECRET, R_URL, PHONE_NO, PIN, TOTP_SECRET = "", "", "", "", "", ""

    # 1. Load from Streamlit secrets.toml (priority)
    try:
        toml_path = os.path.join(".streamlit", "secrets.toml")
        if os.path.exists(toml_path):
            with open(toml_path, 'r') as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split('=', 1)
                        k = k.strip().upper()
                        v = v.strip().strip('"').strip("'")
                        if k == "UPSTOX_PHONE": PHONE_NO = v
                        if k == "UPSTOX_PIN": PIN = v
                        if k == "UPSTOX_API_KEY": API_KEY = v
                        if k == "UPSTOX_API_SECRET": API_SECRET = v
                        if k == "UPSTOX_REDIRECT_URI": R_URL = v
                        if k == "UPSTOX_TOTP_SECRET": TOTP_SECRET = v
    except Exception as e:
        print(f"Error reading secrets file: {e}")

    # 2. Fallback to DB Settings
    if not PHONE_NO: PHONE_NO = db.get_param('upstox_phone', '')
    if not PIN:      PIN = db.get_param('upstox_pin', '')
    if not TOTP_SECRET: TOTP_SECRET = db.get_param('upstox_totp_secret', '')
    if not API_KEY:    API_KEY = db.get_param('upstox_api_key', '')
    if not API_SECRET: API_SECRET = db.get_param('upstox_api_secret', '')
    if not R_URL:      R_URL = db.get_param('upstox_redirect_uri', 'https://127.0.0.1')

    # Ask for missing credentials
    if not PHONE_NO or not PIN or not TOTP_SECRET:
        msg = "Missing UPSTOX_PHONE, UPSTOX_PIN, or UPSTOX_TOTP_SECRET in secrets.toml"
        print(f"\n❌ CRITICAL ERROR: {msg}")
        db.log_system_error("AUTO-LOGIN", msg)
        return

    if not API_KEY or not API_SECRET:
        print("❌ Error: Please set upstox_api_key and upstox_api_secret in the DB first.")
        return

    print("\n[STARTING] Launching Headless Chrome Browser...")
    import platform
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--proxy-server='direct://'")
    chrome_options.add_argument("--proxy-bypass-list=*")
    chrome_options.add_argument("--start-maximized")
    
    if platform.system() == "Linux":
        # Force binary path for stability on VPS
        chrome_options.binary_location = "/usr/bin/google-chrome"

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        msg = f"Failed to start Chrome Driver: {e}"
        print(f"[ERROR] {msg}")
        db.log_system_error("AUTO-LOGIN", msg)
        return

    try:
        # 1. Get Auth URL
        params = {
            'response_type': 'code',
            'client_id': API_KEY,
            'redirect_uri': R_URL
        }
        auth_url = "https://api.upstox.com/v2/login/authorization/dialog?" + urllib.parse.urlencode(params)
        print(f"[NAVIGATING] To Upstox Login...")
        driver.get(auth_url)
        
        # 2. Enter Phone Number
        wait = WebDriverWait(driver, 15)
        print("[PHONE] Entering Phone Number...")
        phone_input = wait.until(EC.presence_of_element_located((By.ID, "mobileNum")))
        phone_input.send_keys(PHONE_NO)
        driver.find_element(By.ID, "getOtp").click()
        
        # 3. Handle OTP (via TOTP or Manual)
        otp_input = wait.until(EC.presence_of_element_located((By.ID, "otpNum")))
        if TOTP_SECRET:
            print("[TOTP] Generating TOTP Automatically...")
            totp = pyotp.TOTP(TOTP_SECRET)
            current_otp = totp.now()
            print(f"   Generated OTP: {current_otp}")
            otp_input.send_keys(current_otp)
        else:
            current_otp = input("[INPUT] Enter the OTP sent to your phone: ").strip()
            otp_input.send_keys(current_otp)
            
        driver.find_element(By.ID, "continueBtn").click()
        
        # 4. Enter PIN
        print("[PIN] Entering PIN...")
        pin_input = wait.until(EC.presence_of_element_located((By.ID, "pinCode")))
        pin_input.send_keys(PIN)
        
        # Wait for Upstox to automatically redirect after PIN
        print("[WAIT] Waiting for Upstox redirection...")
        wait.until(EC.url_contains("code="))
        
        current_url = driver.current_url
        auth_code = current_url.split('code=')[1].split('&')[0]
        print(f"[SUCCESS] Auth Code Extracted!")
        
        # 5. Exchange Auth Code for Access Token
        print("[FETCHING] Final Access Token from Upstox API...")
        token_url = "https://api.upstox.com/v2/login/authorization/token"
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'code': auth_code,
            'client_id': API_KEY,
            'client_secret': API_SECRET,
            'redirect_uri': R_URL,
            'grant_type': 'authorization_code'
        }
        
        response = requests.post(token_url, headers=headers, data=data)
        if response.status_code == 200:
            access_token = response.json().get('access_token')
            if access_token:
                db.set_param('upstox_access_token', access_token)
                
                # Write to secrets.txt
                if os.path.exists('secrets.txt'):
                    with open('secrets.txt', 'a') as f:
                        f.write(f"\nUPSTOX_ACCESS_TOKEN={access_token}\n")
                        
                print("\n" + "="*20)
                print(" [SUCCESS] New Upstox Token Saved!")
                print("="*20)
            else:
                print("[ERROR] Received 200 but no access_token found in response.")
        else:
            print(f"[ERROR] API Error {response.status_code}: {response.text}")

    except Exception as e:
        msg = f"Login flow failed: {e}"
        print(f"\n[ERROR] {msg}")
        db.log_system_error("AUTO-LOGIN", msg)
    finally:
        driver.quit()

if __name__ == "__main__":
    run_auto_login()
