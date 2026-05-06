"""
nifty_executor.py — BHARAT ALGOVERSE v3.0 | Nifty Executor
===========================================================
LEGO BLOCK: Option selection + order execution for NSE Nifty
• Broker: Upstox API v2 (uses token from secrets.txt/DB)
• Strategy: Positional options — BUY CE on BUY, BUY PE on SELL
• Strike Rule: Nearest premium ≈ ₹120 (configurable)
• Expiry Rule: Skip current week → always next week's expiry
• No intraday: all positions held until next signal flip
• Completely isolated from crypto/Delta Exchange code
"""

import requests
import json
import db
from datetime import datetime, date, timedelta
from utils import log_terminal, send_telegram_msg
import pytz

IST      = pytz.timezone("Asia/Kolkata")
BASE_URL = "https://api.upstox.com/v2"


# ── Auth Header ────────────────────────────────────────────
def _headers() -> dict:
    token = db.get_param('upstox_access_token', '')
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


# ============================================================
# LEGO 5: Next-Week Expiry Rule (skip current week)
# ============================================================
def get_next_week_thursday() -> str:
    """
    NSE weekly options expire every Thursday.
    We skip the current week and return the NEXT week's Thursday.
    Format: YYYY-MM-DD
    """
    today = date.today()
    # Find this week's Thursday (weekday 3)
    days_to_thu = (3 - today.weekday()) % 7
    this_thursday = today + timedelta(days=days_to_thu if days_to_thu != 0 else 7)

    # Always go to NEXT Thursday
    next_thursday = this_thursday + timedelta(weeks=1)
    return next_thursday.strftime('%Y-%m-%d')


# ============================================================
# LEGO 6: Fetch Nifty Option Chain (Upstox)
# ============================================================
def fetch_nifty_option_chain(symbol: str = "NSE_INDEX|Nifty 50",
                              expiry: str = None) -> list:
    """
    Fetches Nifty option chain from Upstox v2 API.
    Returns flat list of option contracts.
    """
    if expiry is None:
        expiry = get_next_week_thursday()

    try:
        url    = f"{BASE_URL}/option/chain"
        params = {"instrument_key": symbol, "expiry_date": expiry}
        resp   = requests.get(url, headers=_headers(), params=params, timeout=10)

        if resp.status_code == 200:
            data = resp.json().get('data', [])
            flat = []
            for strike in data:
                sp = float(strike.get('strike_price', 0))
                for opt_type, key in [('CE', 'call_options'), ('PE', 'put_options')]:
                    opt = strike.get(key)
                    if opt:
                        flat.append({
                            'strike':       sp,
                            'type':         opt_type,
                            'ltp':          float(opt.get('market_data', {}).get('ltp', 0)),
                            'instrument':   opt.get('instrument_key', ''),
                            'expiry':       expiry,
                        })
            return flat
        else:
            log_terminal(f"[NIFTY] Option chain fetch failed: {resp.status_code} - {resp.text[:150]}", "ERROR")
            return []

    except Exception as e:
        log_terminal(f"[NIFTY] Option chain exception: {e}", "ERROR")
        return []


# ============================================================
# LEGO 7: Premium-Based Strike Picker (₹120 rule)
# ============================================================
def find_target_premium_option(direction: str, chain: list,
                                target_premium: float = None) -> dict | None:
    """
    Finds the option whose LTP is nearest to target_premium (default ₹120).
    direction: 'BUY' → CE, 'SELL' → PE
    """
    if target_premium is None:
        target_premium = float(db.get_param('nifty_target_premium', '120') or '120')

    opt_type = 'CE' if direction == 'BUY' else 'PE'
    candidates = [o for o in chain if o['type'] == opt_type and o['ltp'] > 5]

    if not candidates:
        return None

    # Nearest LTP to target_premium
    best = min(candidates, key=lambda o: abs(o['ltp'] - target_premium))
    return best


# ============================================================
# LEGO 8: Place Order (Upstox)
# ============================================================
def place_nifty_order(instrument_key: str, qty: int, side: str = 'BUY') -> bool:
    """
    Places market order on Upstox.
    side: 'BUY' or 'SELL'
    qty: number of lots × lot size (default Nifty lot = 25)
    """
    mode = db.get_param('nifty_trade_mode', 'PAPER') or 'PAPER'
    if mode != 'LIVE':
        log_terminal(f"[NIFTY] PAPER MODE: Would place {side} {qty} × {instrument_key}", "TRADE")
        return True

    try:
        payload = {
            "quantity":       qty,
            "product":        "D",           # D = Delivery (positional)
            "validity":       "DAY",
            "price":          0,
            "tag":            "BHARAT-NIFTY",
            "instrument_token": instrument_key,
            "order_type":     "MARKET",
            "transaction_type": side,
            "disclosed_quantity": 0,
            "trigger_price":  0,
            "is_amo":         False,
        }
        resp = requests.post(f"{BASE_URL}/order/place",
                             headers=_headers(),
                             data=json.dumps(payload), timeout=10)

        if resp.status_code in [200, 201]:
            order_id = resp.json().get('data', {}).get('order_id', 'N/A')
            log_terminal(f"[NIFTY] ✅ Order placed: {side} {qty}×{instrument_key} | OrderID={order_id}", "TRADE")
            send_telegram_msg(f"🟢 NIFTY ORDER PLACED\n{side} {qty} × {instrument_key}\nOrderID: {order_id}")
            return True
        else:
            log_terminal(f"[NIFTY] ❌ Order failed: {resp.status_code} - {resp.text[:200]}", "ERROR")
            send_telegram_msg(f"🔴 NIFTY ORDER FAILED\n{resp.text[:200]}")
            return False

    except Exception as e:
        log_terminal(f"[NIFTY] Order exception: {e}", "ERROR")
        return False


# ============================================================
# LEGO 9: Position Sync (Upstox)
# ============================================================
def get_nifty_positions() -> list:
    """Returns list of open Nifty option positions."""
    try:
        resp = requests.get(f"{BASE_URL}/portfolio/positions",
                            headers=_headers(), timeout=10)
        if resp.status_code == 200:
            all_pos = resp.json().get('data', [])
            nifty   = [p for p in all_pos
                       if 'NIFTY' in p.get('trading_symbol', '').upper()
                       and abs(float(p.get('quantity', 0))) > 0]
            return nifty
        return []
    except Exception as e:
        log_terminal(f"[NIFTY] Position sync error: {e}", "ERROR")
        return []


# ============================================================
# LEGO 10: Square Off All Nifty Positions
# ============================================================
def square_off_nifty_all() -> bool:
    """Closes all open Nifty option positions at market price."""
    positions = get_nifty_positions()
    if not positions:
        log_terminal("[NIFTY] No open positions to close.", "INFO")
        db.set_param('nifty_active_symbol', 'NONE')
        db.set_param('nifty_trade_active', 'NO')
        return True

    ok = True
    for p in positions:
        qty   = abs(int(p.get('quantity', 0)))
        inst  = p.get('instrument_token') or p.get('trading_symbol', '')
        side  = 'SELL' if float(p.get('quantity', 0)) > 0 else 'BUY'
        log_terminal(f"[NIFTY] Closing: {inst} | {qty} lots | {side}", "ALERT")
        if not place_nifty_order(inst, qty, side=side):
            ok = False

    if ok:
        db.set_param('nifty_active_symbol', 'NONE')
        db.set_param('nifty_trade_active',  'NO')
        send_telegram_msg("✅ NIFTY: All positions closed.")
    return ok


# ============================================================
# LEGO 11: Main Trade Executor
# ============================================================
def execute_nifty_trade(direction: str) -> bool:
    """
    Full flow: option selection → order placement → DB update.
    direction: 'BUY' (buy CE) | 'SELL' (buy PE)
    """
    # Guard: check no existing position
    if db.get_param('nifty_trade_active', 'NO') == 'YES':
        log_terminal("[NIFTY] Trade already active. Holding.", "INFO")
        return False

    expiry = get_next_week_thursday()
    chain  = fetch_nifty_option_chain(expiry=expiry)

    if not chain:
        log_terminal(f"[NIFTY] Empty option chain for {expiry}.", "ERROR")
        return False

    best = find_target_premium_option(direction, chain)
    if best is None:
        log_terminal(f"[NIFTY] No suitable option found for {direction}.", "ERROR")
        return False

    lots     = int(db.get_param('nifty_lots', '1') or '1')
    lot_size = int(db.get_param('nifty_lot_size', '25') or '25')  # Nifty lot = 25
    qty      = lots * lot_size

    log_terminal(
        f"[NIFTY] Executing {direction}: {best['type']} strike={best['strike']} "
        f"ltp=₹{best['ltp']:.1f} expiry={expiry} qty={qty}", "TRADE"
    )
    send_telegram_msg(
        f"🎯 NIFTY SIGNAL: {direction}\n"
        f"Strike: {best['strike']} {best['type']}\n"
        f"Premium: ₹{best['ltp']:.1f} | Expiry: {expiry}\n"
        f"Lots: {lots} × {lot_size} = {qty} units"
    )

    success = place_nifty_order(best['instrument'], qty, side='BUY')
    if success:
        db.set_param('nifty_trade_active',  'YES')
        db.set_param('nifty_active_symbol', best['instrument'])
        db.set_param('nifty_last_direction', direction)
        db.set_param('nifty_entry_premium', str(best['ltp']))
        db.set_param('nifty_expiry', expiry)
    return success
