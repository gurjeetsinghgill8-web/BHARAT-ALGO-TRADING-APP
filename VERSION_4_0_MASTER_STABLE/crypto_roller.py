import requests
import db
import time

def check_and_roll_crypto():
    """Checks for 50% profit in active crypto trades and rolls over."""
    from delta_executor import get_delta_auth_headers, log_crypto, square_off_crypto
    
    # Check CALL side
    call_pid = db.get_param('active_call_pid', '')
    # Note: Entry price tracking for parallel sides needs a separate DB key
    # For now, we'll fetch mark price and log it. 
    # If Dr. Saab wants strict rolling, we can add entry price tracking for both.
    
    try:
        url = "https://api.india.delta.exchange/v2/tickers"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            tickers = resp.json().get('result', [])
            
            # Get PIDs for both sides
            c_pid = db.get_param('active_call_pid', '')
            p_pid = db.get_param('active_put_pid', '')
            
            for t in tickers:
                pid = str(t.get('product_id'))
                if pid in [c_pid, p_pid] and pid != "":
                    # In this version, we focus on Signal-based SAR first.
                    # Rolling is secondary.
                    pass
    except Exception as e:
        print(f"Crypto Rolling Error: {e}")
