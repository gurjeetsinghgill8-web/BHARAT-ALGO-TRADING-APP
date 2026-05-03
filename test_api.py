import delta_executor
import db
import requests
import json

def test():
    api_key = db.get_param('delta_api_key', '')
    api_secret = db.get_param('delta_api_secret', '')
    
    if not api_key:
        print("ERROR: No API Key in DB.")
        return

    print(f"Testing API Key: {api_key[:5]}...")
    
    url = "https://api.india.delta.exchange/v2/positions"
    try:
        headers = delta_executor.get_delta_auth_headers("GET", "/v2/positions")
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {resp.status_code}")
        if resp.status_code == 200:
            pos = resp.json().get('result', [])
            print(f"Positions: {json.dumps(pos, indent=2)}")
            
            # If no positions, try to PLACE A TEST PAPER-SIZED TRADE (1 contract)
            if not pos:
                print("No positions found. Checking Wallet...")
                url_w = "https://api.india.delta.exchange/v2/wallet/balances"
                h_w = delta_executor.get_delta_auth_headers("GET", "/v2/wallet/balances")
                r_w = requests.get(url_w, headers=h_w)
                print(f"Wallet Status: {r_w.status_code}")
                if r_w.status_code == 200:
                    print("Wallet OK.")
                else:
                    print(f"Wallet Error: {r_w.text}")
        elif resp.status_code == 401:
            print("ERROR: 401 Unauthorized. API Key/Secret is wrong OR IP not whitelisted.")
        else:
            print(f"Error: {resp.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test()
