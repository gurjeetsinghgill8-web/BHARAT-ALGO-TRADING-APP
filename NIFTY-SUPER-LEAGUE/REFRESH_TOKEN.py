"""
SIMPLE_TOKEN_REFRESH.py
========================
Generates the Upstox login URL using the EXACT same method
as the existing working upstox_login.py in the parent folder.
Run from NIFTY-SUPER-LEAGUE folder.
"""
import sys, os, sqlite3, urllib.parse

PARENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TOML   = os.path.join(PARENT, ".streamlit", "secrets.toml")
MAIN_DB= os.path.join(PARENT, "trading_app.db")

# Read keys from TOML (source of truth)
keys = {}
if os.path.exists(TOML):
    with open(TOML, "r") as f:
        for line in f:
            if "=" in line and not line.strip().startswith(("#","[")):
                k, _, v = line.strip().partition("=")
                keys[k.strip().upper()] = v.strip().strip('"').strip("'")

API_KEY      = keys.get("UPSTOX_API_KEY", "")
API_SECRET   = keys.get("UPSTOX_API_SECRET", "")
REDIRECT_URI = keys.get("UPSTOX_REDIRECT_URI", "https://127.0.0.1")

print("="*60)
print(" NIFTY SUPER LEAGUE - Token Refresh")
print("="*60)
print(f"\n API Key      : {API_KEY}")
print(f" Redirect URI : {REDIRECT_URI}")
print()

if not API_KEY:
    print("ERROR: UPSTOX_API_KEY not found in secrets.toml")
    sys.exit(1)

# Build auth URL
params   = {"response_type": "code", "client_id": API_KEY, "redirect_uri": REDIRECT_URI}
auth_url = "https://api.upstox.com/v2/login/authorization/dialog?" + urllib.parse.urlencode(params)

print("STEP 1: Open this URL in Chrome/Edge browser:")
print(f"\n  {auth_url}\n")
print("STEP 2: Login with your phone + OTP + PIN")
print(f"STEP 3: Browser will go to {REDIRECT_URI}/?code=XXXXXX")
print("        (page may show error - that's fine)")
print("STEP 4: Copy the 'code' from the URL and paste below\n")

code = input("Paste the code here: ").strip()
if not code:
    print("No code entered.")
    sys.exit(1)

# Exchange code for token
import requests
print("\nFetching token...")
resp = requests.post(
    "https://api.upstox.com/v2/login/authorization/token",
    headers={"accept":"application/json","Content-Type":"application/x-www-form-urlencoded"},
    data={"code":code,"client_id":API_KEY,"client_secret":API_SECRET,
          "redirect_uri":REDIRECT_URI,"grant_type":"authorization_code"},
    timeout=15
)

if resp.status_code == 200:
    token = resp.json().get("access_token","")
    if token:
        # Save to TOML
        import re
        with open(TOML, "r") as f:
            content = f.read()
        new_line = f'UPSTOX_ACCESS_TOKEN = "{token}"'
        if re.search(r"UPSTOX_ACCESS_TOKEN", content, re.IGNORECASE):
            content = re.sub(r"UPSTOX_ACCESS_TOKEN\s*=.*", new_line, content, flags=re.IGNORECASE)
        else:
            content += f"\n{new_line}\n"
        with open(TOML, "w") as f:
            f.write(content)
        print(f"\nSUCCESS! Token saved to secrets.toml")

        # Save to NSL DB
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import nsl_db as db
        db.set("upstox_access_token", token)
        print("SUCCESS! Token saved to nsl_trader.db")
        print("\nYou can now start the engine (START.bat)")
    else:
        print("Error: No token in response")
        print(resp.text)
else:
    print(f"Error {resp.status_code}: {resp.text}")
