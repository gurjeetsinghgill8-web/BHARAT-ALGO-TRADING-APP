"""
nsl_executor.py — NIFTY SUPER LEAGUE | LEGO 6: Order Engine
=============================================================
Handles all Upstox order placement for Nifty 50 options.

RULES:
  • Always BUYING options (CE for CALL, PE for PUT)
  • Strike: premium range ₹100–₹120, pick HIGHEST LTP in range
  • Expiry: next upcoming expiry from exchange API
  • Order type: MARKET | Product: I (Intraday)
  • LOT GUARD: NEVER more than MAX_ALLOWED_LOTS (1) on exchange
  • FLIP EXIT: close ALL open NSE_FO positions (not just DB symbol)
  • Grace period: skip zombie check within ENTRY_GRACE_PERIOD_SECS of entry
  • Idempotency: double-check exchange before every entry — never stack
"""

import requests
import json
import time
from datetime import date, timedelta
from typing import Optional

import nsl_db as db
import nsl_config as cfg
import nsl_utils as utils
import nsl_telegram as tg


def _headers() -> dict:
    token = db.get("upstox_access_token", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


# ─────────────────────────────────────────────────────────────
# Expiry calculation
# ─────────────────────────────────────────────────────────────
def get_candidate_expiries() -> list[str]:
    """
    Returns up to 3 next expiry dates after today from exchange API.
    Falls back to next 3 Thursdays if API fails.
    """
    try:
        token = db.get("upstox_access_token", "")
        resp  = requests.get(
            f"{cfg.UPSTOX_BASE}/option/contract",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"instrument_key": cfg.NIFTY_INST_KEY},
            timeout=10,
            proxies=db.get_proxy()
        )
        if resp.status_code == 200:
            data     = resp.json().get("data", [])
            expiries = sorted(set(x["expiry"] for x in data if x.get("expiry")))
            today    = date.today()
            result   = [exp for exp in expiries if date.fromisoformat(exp) > today][:3]
            if result:
                utils.log(f"Candidate expiries from API: {result}", "INFO")
                return result
    except Exception as e:
        utils.log(f"Expiry API failed: {e} — using fallback", "WAIT")

    # Fallback: next 3 Thursdays
    today   = date.today()
    out     = []
    current = today
    while len(out) < 3:
        current = current + timedelta(days=1)
        if current.weekday() == 3:   # Thursday
            out.append(current.strftime("%Y-%m-%d"))
    utils.log(f"Fallback expiries (next 3 Thursdays): {out}", "WAIT")
    return out


def get_next_expiry() -> str:
    """Convenience wrapper — returns the first candidate expiry."""
    return get_candidate_expiries()[0]


# ─────────────────────────────────────────────────────────────
# Option chain fetch
# ─────────────────────────────────────────────────────────────
def fetch_option_chain(expiry: str) -> list[dict]:
    """
    Fetches Nifty 50 option chain for the given expiry.
    Returns flat list of {strike, type, ltp, instrument_key, expiry}.
    """
    try:
        resp = requests.get(
            f"{cfg.UPSTOX_BASE}/option/chain",
            headers=_headers(),
            params={"instrument_key": cfg.NIFTY_INST_KEY, "expiry_date": expiry},
            timeout=12,
            proxies=db.get_proxy()
        )
        if resp.status_code == 200:
            flat = []
            for strike_data in resp.json().get("data", []):
                sp = float(strike_data.get("strike_price", 0))
                for opt_type, key in [("CE", "call_options"), ("PE", "put_options")]:
                    opt = strike_data.get(key)
                    if opt:
                        mkt  = opt.get("market_data", {}) or {}
                        ltp  = float(mkt.get("ltp", 0) or mkt.get("last_price", 0) or 0)
                        inst = opt.get("instrument_key", "")
                        if inst:
                            flat.append({
                                "strike":         sp,
                                "type":           opt_type,
                                "ltp":            ltp,
                                "instrument_key": inst,
                                "expiry":         expiry,
                            })
            return flat

        utils.log(f"Option chain failed: {resp.status_code} {resp.text[:100]}", "ERROR")
        return []

    except Exception as e:
        utils.log(f"fetch_option_chain exception: {e}", "ERROR")
        return []


# ─────────────────────────────────────────────────────────────
# Strike picker (₹100–₹120, highest LTP)
# ─────────────────────────────────────────────────────────────
def find_best_strike(direction: str, chain: list[dict]) -> Optional[dict]:
    """
    CALL → CE options | PUT → PE options
    Filter to premium range [min, max] (default ₹100–₹120).
    Returns option with HIGHEST LTP in that range.
    """
    premium_min = float(db.get("premium_min", str(cfg.DEFAULT_PREMIUM_MIN)) or cfg.DEFAULT_PREMIUM_MIN)
    premium_max = float(db.get("premium_max", str(cfg.DEFAULT_PREMIUM_MAX)) or cfg.DEFAULT_PREMIUM_MAX)
    opt_type    = "CE" if direction == "CALL" else "PE"

    candidates = [
        o for o in chain
        if o["type"] == opt_type and premium_min <= o["ltp"] <= premium_max
    ]

    if not candidates:
        utils.log(
            f"No {opt_type} in ₹{premium_min:.0f}–₹{premium_max:.0f} range. "
            f"Will widen search ±₹20.",
            "WAIT"
        )
        # Widen range by ₹20 each side and retry once
        candidates = [
            o for o in chain
            if o["type"] == opt_type
            and (premium_min - 20) <= o["ltp"] <= (premium_max + 20)
        ]
        if not candidates:
            utils.log(f"Still no {opt_type} found after widening range.", "ERROR")
            return None

    best = max(candidates, key=lambda o: o["ltp"])
    utils.log(
        f"Best strike: {best['strike']} {opt_type} @ ₹{best['ltp']:.2f} "
        f"(expiry {best['expiry']})",
        "OK"
    )
    return best


# ─────────────────────────────────────────────────────────────
# Place BUY order
# ─────────────────────────────────────────────────────────────
def place_buy_order(instrument_key: str, qty: int) -> bool:
    """Places a MARKET BUY order for an option contract."""
    try:
        lot_size = int(db.get("lot_size", str(cfg.DEFAULT_LOT_SIZE)) or cfg.DEFAULT_LOT_SIZE)
        if qty % lot_size != 0:
            utils.log(f"LOT SIZE ERROR: qty={qty} not multiple of {lot_size}. Correcting.", "ERROR")
            qty = max(lot_size, (qty // lot_size) * lot_size)

        payload = {
            "quantity":           qty,
            "product":            "I",
            "validity":           "DAY",
            "price":              0,
            "tag":                "NSL-ENTRY",
            "instrument_token":   instrument_key,
            "order_type":         "MARKET",
            "transaction_type":   "BUY",
            "disclosed_quantity": 0,
            "trigger_price":      0,
            "is_amo":             False,
        }
        resp = requests.post(
            f"{cfg.UPSTOX_BASE}/order/place",
            headers=_headers(),
            data=json.dumps(payload),
            timeout=12,
            proxies=db.get_proxy(),
        )
        if resp.status_code in [200, 201]:
            order_id = resp.json().get("data", {}).get("order_id", "N/A")
            utils.log(f"BUY ORDER PLACED: {instrument_key} × {qty} | OrderID={order_id}", "TRADE")
            return True
        else:
            utils.log(f"BUY ORDER FAILED: {resp.status_code} {resp.text[:200]}", "ERROR")
            tg.send_msg(tg.msg_error("BUY ORDER", resp.text[:200]))
            return False

    except Exception as e:
        utils.log(f"place_buy_order exception: {e}", "ERROR")
        tg.send_msg(tg.msg_error("BUY ORDER", str(e)))
        return False


# ─────────────────────────────────────────────────────────────
# Place SELL order
# ─────────────────────────────────────────────────────────────
def place_sell_order(instrument_key: str, qty: int) -> bool:
    """Places a MARKET SELL order to square off an existing BUY position."""
    try:
        lot_size = int(db.get("lot_size", str(cfg.DEFAULT_LOT_SIZE)) or cfg.DEFAULT_LOT_SIZE)
        if qty % lot_size != 0:
            qty = max(lot_size, (qty // lot_size) * lot_size)

        payload = {
            "quantity":           qty,
            "product":            "I",
            "validity":           "DAY",
            "price":              0,
            "tag":                "NSL-EXIT",
            "instrument_token":   instrument_key,
            "order_type":         "MARKET",
            "transaction_type":   "SELL",
            "disclosed_quantity": 0,
            "trigger_price":      0,
            "is_amo":             False,
        }
        resp = requests.post(
            f"{cfg.UPSTOX_BASE}/order/place",
            headers=_headers(),
            data=json.dumps(payload),
            timeout=12,
            proxies=db.get_proxy(),
        )
        if resp.status_code in [200, 201]:
            order_id = resp.json().get("data", {}).get("order_id", "N/A")
            utils.log(f"SELL ORDER PLACED: {instrument_key} × {qty} | OrderID={order_id}", "TRADE")
            return True
        else:
            utils.log(f"SELL ORDER FAILED: {resp.status_code} {resp.text[:200]}", "ERROR")
            tg.send_msg(tg.msg_error("SELL ORDER", resp.text[:200]))
            return False

    except Exception as e:
        utils.log(f"place_sell_order exception: {e}", "ERROR")
        tg.send_msg(tg.msg_error("SELL ORDER", str(e)))
        return False


# ─────────────────────────────────────────────────────────────
# Get ALL open NSE_FO positions (exchange truth)
# ─────────────────────────────────────────────────────────────
def get_all_nse_fo_positions() -> list[dict]:
    """
    Returns ALL open intraday NSE_FO positions from exchange.
    This is the RAW truth — used by lot guard, flip exit, startup sync.
    """
    try:
        resp = requests.get(
            f"{cfg.UPSTOX_BASE}/portfolio/short-term-positions",
            headers=_headers(), timeout=10, proxies=db.get_proxy()
        )
        if resp.status_code == 200:
            all_pos = resp.json().get("data", [])
            return [
                p for p in all_pos
                if abs(float(p.get("quantity", 0))) > 0
                and p.get("product", "") == "I"
                and "NSE_FO" in p.get("instrument_token", "")
            ]
        elif resp.status_code == 401:
            utils.log("Upstox token expired (401). Update token from dashboard!", "ALERT")
        return []
    except Exception as e:
        utils.log(f"get_all_nse_fo_positions exception: {e}", "ERROR")
        return []


# ─────────────────────────────────────────────────────────────
# LOT INTEGRITY GUARD — max 1 lot enforced every cycle
# ─────────────────────────────────────────────────────────────
def enforce_lot_integrity() -> bool:
    """
    Checks ALL open NSE_FO positions on exchange every cycle.
    If more than MAX_ALLOWED_LOTS found → close ALL excess immediately.
    Returns True if OK (0 or 1 lot).
    Returns False if excess was found and fixed — engine skips this cycle.

    Grace period: skipped within ENTRY_GRACE_PERIOD_SECS of a new entry.
    """
    entry_ts = float(db.get("entry_timestamp_epoch", "0") or "0")
    if entry_ts > 0:
        age_secs = time.time() - entry_ts
        if age_secs < cfg.ENTRY_GRACE_PERIOD_SECS:
            utils.log(
                f"LOT GUARD: Grace period active ({age_secs:.0f}s / {cfg.ENTRY_GRACE_PERIOD_SECS}s). Skipping.",
                "GUARD"
            )
            return True

    positions = get_all_nse_fo_positions()
    lot_size  = int(db.get("lot_size", str(cfg.DEFAULT_LOT_SIZE)) or cfg.DEFAULT_LOT_SIZE)

    if not positions:
        if db.get("trade_active") == "YES":
            utils.log("LOT GUARD: Exchange flat but DB says active — clearing stale state.", "ALERT")
            _clear_trade_db()
        return True

    total_lots = sum(
        abs(int(float(p.get("quantity", 0)))) // lot_size
        for p in positions
    )

    utils.log(f"LOT GUARD: {total_lots} lot(s) on exchange ({len(positions)} position(s)).", "GUARD")

    if total_lots <= cfg.MAX_ALLOWED_LOTS:
        # Sync DB with exchange reality
        pos  = positions[0]
        sym  = pos.get("instrument_token", "NONE")
        name = pos.get("trading_symbol", "")
        dir_ = "CALL" if "CE" in name else "PUT" if "PE" in name else db.get("active_option_type", "NONE")
        if db.get("trade_active") != "YES":
            db.set("trade_active",       "YES")
            db.set("active_symbol",      sym)
            db.set("active_option_type", dir_)
        return True

    # EXCESS LOTS — close all immediately
    utils.log(
        f"LOT GUARD 🚨 EXCESS! {total_lots} lots found (max={cfg.MAX_ALLOWED_LOTS}). "
        f"Closing ALL {len(positions)} position(s)!",
        "ALERT"
    )
    tg.send_msg(
        f"🚨 <b>LOT INTEGRITY BREACH!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Found {total_lots} lots (max allowed: {cfg.MAX_ALLOWED_LOTS})\n"
        f"Closing ALL {len(positions)} position(s) immediately!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Emergency safety action."
    )

    for pos in positions:
        sym = pos.get("instrument_token", "NONE")
        qty = abs(int(float(pos.get("quantity", 0))))
        if qty > 0 and sym != "NONE":
            ok = place_sell_order(sym, qty)
            if not ok:
                utils.log(f"LOT GUARD: Failed to close {sym} × {qty}!", "ERROR")

    _clear_trade_db()
    return False


# ─────────────────────────────────────────────────────────────
# Square off ALL (used on flip / force close)
# ─────────────────────────────────────────────────────────────
def square_off_all_positions() -> bool:
    """
    Closes ALL open NSE_FO intraday positions on exchange.
    Used on signal flip and 3:10 PM force close.
    Returns True if all closed (or already flat).
    """
    positions = get_all_nse_fo_positions()
    if not positions:
        utils.log("square_off_all: Already flat on exchange.", "INFO")
        _clear_trade_db()
        return True

    utils.log(f"square_off_all: Closing {len(positions)} position(s)...", "TRADE")
    all_ok = True
    for pos in positions:
        sym = pos.get("instrument_token", "NONE")
        qty = abs(int(float(pos.get("quantity", 0))))
        if qty > 0 and sym != "NONE":
            ok = place_sell_order(sym, qty)
            if not ok:
                all_ok = False
                utils.log(f"square_off_all: FAILED to close {sym} × {qty}", "ERROR")
            else:
                utils.log(f"square_off_all: Closed {sym} × {qty}", "TRADE")

    _clear_trade_db()
    return all_ok


# ─────────────────────────────────────────────────────────────
# Clear trade DB state
# ─────────────────────────────────────────────────────────────
def _clear_trade_db() -> None:
    """Clears all active trade state from DB after a square-off."""
    db.set("trade_active",          "NO")
    db.set("active_symbol",         "NONE")
    db.set("active_option_type",    "NONE")
    db.set("active_trading_label",  "")      # v4.1: human-readable label
    db.set("entry_premium",         "0")
    db.set("entry_time",            "")
    db.set("entry_timestamp_epoch", "0")
    db.set("current_option_ltp",    "0")
    db.set("unrealized_pnl_pct",    "0")
    db.set("ltp_fetch_failed",      "NO")    # v4.1: clear LTP error flag


# ─────────────────────────────────────────────────────────────
# Full entry flow (with idempotency guard)
# ─────────────────────────────────────────────────────────────
def execute_entry(direction: str) -> bool:
    """
    Full entry flow:
      1. DB guard — abort if already marked active
      2. Exchange guard — abort if exchange already has open position
      3. Get next expiry
      4. Fetch option chain
      5. Find best strike (₹100–₹120, highest LTP)
      6. Place BUY MARKET order
      7. Update DB + set grace period timestamp

    direction: 'CALL' or 'PUT'
    """
    # Guard 1: DB says already active
    if db.get("trade_active") == "YES":
        utils.log("ENTRY BLOCKED: DB already active — skipping.", "GUARD")
        return False

    # Guard 2: Exchange already has open position (idempotency)
    exchange_pos = get_all_nse_fo_positions()
    if exchange_pos:
        pos  = exchange_pos[0]
        sym  = pos.get("instrument_token", "NONE")
        name = pos.get("trading_symbol", "")
        dir_ = "CALL" if "CE" in name else "PUT" if "PE" in name else "NONE"
        utils.log(
            f"ENTRY BLOCKED: Exchange already has {len(exchange_pos)} open position(s). "
            f"Syncing DB and skipping new entry.",
            "GUARD"
        )
        db.set("trade_active",       "YES")
        db.set("active_symbol",      sym)
        db.set("active_option_type", dir_)
        return False

    # Try each candidate expiry until we get a non-empty chain
    expiry_candidates = get_candidate_expiries()
    chain  = []
    expiry = expiry_candidates[0]
    for exp in expiry_candidates:
        utils.log(f"Trying expiry: {exp}", "INFO")
        chain = fetch_option_chain(exp)
        if chain:
            expiry = exp
            utils.log(f"Using expiry {expiry} — {len(chain)} options found", "OK")
            break
        utils.log(f"Empty chain for {exp} — trying next expiry...", "WAIT")

    if not chain:
        utils.log(f"No valid chain for any expiry: {expiry_candidates}. Cannot enter.", "ERROR")
        tg.send_msg(tg.msg_error("ENTRY", f"Empty chain for all expiries: {expiry_candidates}"))
        return False

    best = find_best_strike(direction, chain)
    if best is None:
        utils.log(f"No suitable strike found for {direction}.", "ERROR")
        tg.send_msg(tg.msg_error("ENTRY", f"No strike in range for {direction}"))
        return False

    lots     = int(db.get("lots",     str(cfg.DEFAULT_LOTS))     or cfg.DEFAULT_LOTS)
    lot_size = int(db.get("lot_size", str(cfg.DEFAULT_LOT_SIZE)) or cfg.DEFAULT_LOT_SIZE)
    qty      = lots * lot_size

    success = place_buy_order(best["instrument_key"], qty)
    if success:
        now_epoch = time.time()
        # Build human-readable label for dashboard display
        label = f"{best['strike']:.0f} {best['type']} | Exp: {expiry}"
        db.set("trade_active",          "YES")
        db.set("active_symbol",         best["instrument_key"])
        db.set("active_option_type",    direction)
        db.set("active_trading_label",  label)          # v4.1
        db.set("entry_premium",         str(best["ltp"]))
        db.set("entry_time",            utils.fmt_time())
        db.set("entry_timestamp_epoch", str(now_epoch))
        db.set("ltp_fetch_failed",      "NO")           # v4.1: clear on fresh entry

        ltp    = float(db.get("current_ltp", "0") or "0")
        st_val = float(db.get("st_value",    "0") or "0")
        st_dir = db.get("st_direction", "NONE")

        tg.send_msg(tg.msg_entry(
            direction, best["strike"], best["type"],
            best["ltp"], expiry, lots, lot_size, ltp, st_val, st_dir
        ))
        utils.log(
            f"Entry complete: {direction} {best['strike']} {best['type']} "
            f"@ Rs.{best['ltp']:.2f} | Grace period: {cfg.ENTRY_GRACE_PERIOD_SECS}s",
            "TRADE"
        )

    return success

