import time
import hmac
import hashlib
import requests
import datetime
import socket
import db
import pandas as pd
import json
from utils import log_terminal, send_telegram_msg

# --- FORCE IPv4 GLOBALLY (V3 Stable Feature) ---
import requests.packages.urllib3.util.connection as urllib3_cn
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

# --- V3 COMPATIBILITY HELPERS ---
def fetch_btc_spot():
    """V3 Alias for current BTC price."""
    df, _ = fetch_delta_candles("BTC", "1m", limit=1)
    if not df.empty:
        return float(df['close'].iloc[-1])
    return 0

def fetch_premium(symbol):
    """Fetch current mark price (premium) for a specific symbol."""
    try:
        url = f"https://api.india.delta.exchange/v2/tickers/{symbol}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return float(resp.json().get('result', {}).get('mark_price', 0))
    except: pass
    return 0

def fetch_open_positions():
    """Helper to fetch raw positions from Delta API."""
    try:
        path = "/v2/positions"
        query = "?underlying_asset_symbol=BTC"
        headers = get_delta_auth_headers("GET", path, query_string=query)
        resp = requests.get(f"https://api.india.delta.exchange{path}{query}", headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('result', [])
    except: pass
    return []

def get_current_position():
    try:
        positions = fetch_open_positions()
        if not positions: return None
        for pos in positions:
            size = abs(float(pos.get('size', 0)))
            if size == 0: continue
            
            sym = str(pos.get('symbol') or pos.get('product', {}).get('symbol', '')).upper()
            if sym.startswith('P-') or '-P-' in sym:
                return {
                    'symbol': pos.get('symbol') or pos.get('product', {}).get('symbol'),
                    'type': 'PUT',
                    'entry_price': float(pos.get('avg_entry_price', 0) or 0)
                }
            elif sym.startswith('C-') or '-C-' in sym:
                return {
                    'symbol': pos.get('symbol') or pos.get('product', {}).get('symbol'),
                    'type': 'CALL',
                    'entry_price': float(pos.get('avg_entry_price', 0) or 0)
                }
    except Exception as e:
        print(f"[Pos Error] {e}")
    return None

def fetch_wallet_balance():
    """Fetch USDT balance for safety check."""
    try:
        path = "/v2/wallet/balances"
        headers = get_delta_auth_headers("GET", path)
        resp = requests.get(f"https://api.india.delta.exchange{path}", headers=headers, timeout=10)
        if resp.status_code == 200:
            for b in resp.json().get('result', []):
                if b.get('asset_symbol') == 'USDT':
                    return float(b.get('balance', 0))
    except: pass
    return 0.0

def execute_crypto_trade(asset, direction=None):
    if direction is None:
        direction = asset
        asset = "BTC"
    
    # Balance Safety Guard
    balance = fetch_wallet_balance()
    if balance < 5.0: # $5 minimum safety
        log_terminal(f"⚠️ SAFETY BLOCK: Balance too low (${balance:.2f}). Deposit USDT.", "ERROR")
        return

    # Map V3 strings to V4 directions
    trade_dir = "SELL" if direction == "SELL_CALL" else "BUY"

    if db.get_param('trade_mode', 'PAPER') != "LIVE":
        log_terminal(f"PAPER ENTRY: {direction}", "TRADE"); return
    
    opt = find_gill_crypto_option(asset, trade_dir)
    if not opt:
        log_terminal(f"ERROR: No {direction} option found.", "ERROR"); return
    
    payload = json.dumps({"product_id": int(opt['product_id']), "size": int(db.get_param('crypto_trade_size', '1')), "side": "sell", "order_type": "market_order"})
    headers = get_delta_auth_headers("POST", "/v2/orders", payload=payload)
    resp = requests.post("https://api.india.delta.exchange/v2/orders", headers=headers, data=payload, timeout=10)
    
    if resp.status_code in [200, 201]:
        log_terminal(f"✅ LIVE SELL: {opt['symbol']}", "TRADE")
        sync_delta_position()
    else:
        err_msg = resp.text.lower()
        if "insufficientmargin" in err_msg:
            log_terminal("🚨 MARGIN ERROR: Insufficient funds. Cooling down for 10 mins.", "ERROR")
            config.set_param("last_trade_time", str(time.time() + 600)) # Force 10 min wait
        else:
            log_terminal(f"❌ FAILED: {resp.text}", "ERROR")

def reconcile_bracket_orders(): pass
