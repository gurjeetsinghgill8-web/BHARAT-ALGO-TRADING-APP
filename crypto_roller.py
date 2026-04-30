import requests
import db
import time

def check_and_roll_crypto():
    """Checks for 50% profit in active crypto trade and rolls over."""
    active_id = db.get_param('crypto_active_product_id', '')
    entry_price = float(db.get_param('crypto_active_entry_price', '0'))
    if not active_id or entry_price <= 0: return

    try:
        from delta_executor import get_delta_auth_headers, log_crypto, square_off_crypto
        url = "https://api.india.delta.exchange/v2/tickers"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            tickers = resp.json().get('result', [])
            for t in tickers:
                if str(t.get('product_id')) == str(active_id):
                    mark_price = float(t.get('mark_price', 0))
                    if mark_price >= entry_price * 1.5:
                        log_crypto(f"!!! CRYPTO ROLLING !!! Mark {mark_price} reached 50% target (Entry: {entry_price}).")
                        square_off_crypto()
    except Exception as e:
        print(f"Crypto Rolling Error: {e}")

# SUPREME CLOUD SYNC: 2026-04-30
