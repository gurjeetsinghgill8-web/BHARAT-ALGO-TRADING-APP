import requests
import db
import time
import hmac
import hashlib

def get_headers(method, path, payload=""):
    api_key = db.get_param('delta_api_key', '')
    api_secret = db.get_param('delta_api_secret', '')
    timestamp = str(int(time.time()))
    signature_data = method + timestamp + path + payload
    signature = hmac.new(api_secret.encode('utf-8'), signature_data.encode('utf-8'), hashlib.sha256).hexdigest()
    return {
        'api-key': api_key,
        'signature': signature,
        'timestamp': timestamp,
        'Content-Type': 'application/json'
    }

def test_api():
    paths = ["/v2/positions", "/v2/positions?page_size=10", "/v2/wallet/balances"]
    base = "https://api.india.delta.exchange"
    
    for p in paths:
        url = base + p
        print(f"\n--- Testing {url} ---")
        try:
            headers = get_headers("GET", p)
            resp = requests.get(url, headers=headers, timeout=10)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_api()
