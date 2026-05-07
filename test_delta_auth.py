import os
import hmac
import hashlib
import requests
import time
import json

def get_auth_headers(api_key, api_secret, method, path, query_string="", payload=""):
    timestamp = str(int(time.time()))
    signature_data = method + timestamp + path + query_string + payload
    signature = hmac.new(api_secret.encode('utf-8'), signature_data.encode('utf-8'), hashlib.sha256).hexdigest()
    return {
        'api-key': api_key,
        'signature': signature,
        'timestamp': timestamp,
        'Content-Type': 'application/json'
    }

api_key = "YrtIHAjIVxOQTsZb5dB7JjhaTQbaBq"
api_secret = "a4PGqRaHuIT4eK6oW7pNMkVhGrgjQm6Xmje2ZOqwk77auOa6zrsC3mLG9Kuc"

# Test 1: Delta India
print("Testing Delta India...")
path = "/v2/wallet/balances"
url = f"https://api.india.delta.exchange{path}"
headers = get_auth_headers(api_key, api_secret, "GET", path)
resp = requests.get(url, headers=headers)
print(f"India Response: {resp.status_code} - {resp.text}")

# Test 2: Delta Global
print("\nTesting Delta Global...")
url = f"https://api.delta.exchange{path}"
headers = get_auth_headers(api_key, api_secret, "GET", path)
resp = requests.get(url, headers=headers)
print(f"Global Response: {resp.status_code} - {resp.text}")
