import hmac
import hashlib
import requests
import time
import sqlite3
import os

DB_NAME = "trading_app.db"

def get_param(key):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else ""
    except: return ""

def get_headers(method, endpoint, payload, api_key, api_secret):
    timestamp = str(int(time.time()))
    signature_data = method + timestamp + endpoint + payload
    signature = hmac.new(api_secret.encode('utf-8'), signature_data.encode('utf-8'), hashlib.sha256).hexdigest()
    return {
        'api-key': api_key,
        'signature': signature,
        'timestamp': timestamp,
        'Content-Type': 'application/json'
    }

def emergency_close():
    api_key = get_param('delta_api_key')
    api_secret = get_param('delta_api_secret')
    base_url = "https://api.india.delta.exchange"
    
    if not api_key or not api_secret:
        print("ERROR: API Keys not found in DB.")
        return

    print(f"EMERGENCY: Closing all positions for {api_key[:5]}...")

    # 1. Get Positions
    endpoint = "/v2/positions"
    headers = get_headers("GET", endpoint, "", api_key, api_secret)
    resp = requests.get(base_url + endpoint, headers=headers)
    
    if resp.status_code == 200:
        positions = resp.json().get('result', [])
        found = False
        for p in positions:
            size = float(p.get('size', 0))
            if size != 0:
                found = True
                pid = p.get('product_id')
                symbol = p.get('product', {}).get('symbol', 'Unknown')
                print(f"Closing {symbol} (Size: {size})...")
                
                # Close Order
                order_payload = '{"product_id":' + str(pid) + ',"size":' + str(abs(int(size))) + ',"side":"sell","order_type":"market_order","close_on_trigger":true}'
                headers = get_headers("POST", "/v2/orders", order_payload, api_key, api_secret)
                close_resp = requests.post(base_url + "/v2/orders", headers=headers, data=order_payload)
                print(f"DONE: {symbol} Close Status: {close_resp.status_code}")
        
        if not found:
            print("No active positions found.")
    else:
        print(f"Failed to fetch positions: {resp.status_code}")

if __name__ == "__main__":
    emergency_close()
    # Reset DB Status
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Reset all tracking parameters
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('crypto_active_symbol', 'NONE')")
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('active_call_symbol', 'NONE')")
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('active_put_symbol', 'NONE')")
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('signal_target', 'WAIT')")
        conn.commit()
        conn.close()
        print("🧹 Database Settings Reset to SAFE mode.")
    except Exception as e:
        print(f"DB Reset Error: {e}")
