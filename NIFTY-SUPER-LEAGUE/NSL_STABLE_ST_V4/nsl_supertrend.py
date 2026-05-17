"""
nsl_supertrend.py — NIFTY SUPER LEAGUE | LEGO 5: SuperTrend Engine
====================================================================
Pure SuperTrend calculation on 5-minute CLOSED candles.

RULES:
  • Always uses the closed candle list (forming candle already dropped by nsl_data.py)
  • Minimum ST_MIN_CANDLES required for a valid signal
  • BULLISH = close > SuperTrend line → BUY CALL
  • BEARISH = close < SuperTrend line → BUY PUT
  • Default: Period=10, Multiplier=1.0

HEALTH:
  • st_health = 'OK'    → computed successfully this cycle
  • st_health = 'STALE' → last update was >15 min ago
  • st_health = 'ERROR' → computation failed
"""

import time
from typing import Optional

import nsl_db as db
import nsl_config as cfg
import nsl_utils as utils


# ─────────────────────────────────────────────────────────────
# ATR — Wilder's Smoothing
# ─────────────────────────────────────────────────────────────
def _compute_atr(candles: list[dict], period: int) -> list[float]:
    """Computes ATR using Wilder's smoothing. Returns list same length as candles."""
    if len(candles) < period + 1:
        return [0.0] * len(candles)

    trs = []
    for i, c in enumerate(candles):
        if i == 0:
            tr = c["high"] - c["low"]
        else:
            prev_close = candles[i - 1]["close"]
            tr = max(
                c["high"] - c["low"],
                abs(c["high"] - prev_close),
                abs(c["low"]  - prev_close),
            )
        trs.append(tr)

    atrs = [0.0] * len(candles)
    atrs[period - 1] = sum(trs[:period]) / period
    for i in range(period, len(candles)):
        atrs[i] = (atrs[i - 1] * (period - 1) + trs[i]) / period

    return atrs


# ─────────────────────────────────────────────────────────────
# SuperTrend Core Calculation
# ─────────────────────────────────────────────────────────────
def compute_supertrend(candles: list[dict],
                       period: int,
                       multiplier: float) -> list[dict]:
    """
    Computes SuperTrend for a list of CLOSED candles.
    Returns list of dicts: {timestamp, close, st_value, direction}
    Returns [] if not enough candles.
    """
    n = len(candles)
    if n < period + 1:
        return []

    atrs = _compute_atr(candles, period)

    basic_upper = [(c["high"] + c["low"]) / 2 + multiplier * atrs[i]
                   for i, c in enumerate(candles)]
    basic_lower = [(c["high"] + c["low"]) / 2 - multiplier * atrs[i]
                   for i, c in enumerate(candles)]

    final_upper = [0.0] * n
    final_lower = [0.0] * n
    directions  = ["BULLISH"] * n
    st_values   = [0.0] * n

    for i in range(n):
        if i < period:
            final_upper[i] = basic_upper[i]
            final_lower[i] = basic_lower[i]
            directions[i]  = "BULLISH"
            st_values[i]   = basic_lower[i]
            continue

        # Final upper band
        if basic_upper[i] < final_upper[i - 1] or candles[i - 1]["close"] > final_upper[i - 1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i - 1]

        # Final lower band
        if basic_lower[i] > final_lower[i - 1] or candles[i - 1]["close"] < final_lower[i - 1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i - 1]

        # Direction
        close    = candles[i]["close"]
        prev_dir = directions[i - 1]

        if prev_dir == "BEARISH" and close > final_upper[i]:
            directions[i] = "BULLISH"
        elif prev_dir == "BULLISH" and close < final_lower[i]:
            directions[i] = "BEARISH"
        else:
            directions[i] = prev_dir

        # SuperTrend line value
        if directions[i] == "BULLISH":
            st_values[i] = final_lower[i]
        else:
            st_values[i] = final_upper[i]

    results = []
    for i, c in enumerate(candles):
        if i >= period:
            results.append({
                "timestamp": c["timestamp"],
                "close":     c["close"],
                "st_value":  round(st_values[i], 2),
                "direction": directions[i],
            })

    return results


# ─────────────────────────────────────────────────────────────
# Compute & Store — called every new candle cycle
# ─────────────────────────────────────────────────────────────
def compute_and_store(candles: list[dict]) -> Optional[dict]:
    """
    Runs SuperTrend on closed candles, stores result in DB.
    Returns latest result dict, or None if failed.
    """
    try:
        period     = int(db.get("st_period",     str(cfg.DEFAULT_ST_PERIOD))     or cfg.DEFAULT_ST_PERIOD)
        multiplier = float(db.get("st_multiplier", str(cfg.DEFAULT_ST_MULTIPLIER)) or cfg.DEFAULT_ST_MULTIPLIER)

        if not candles:
            db.set("st_health",    "STALE")
            db.set("st_direction", "NONE")
            utils.log("SuperTrend: no candle data → STALE", "WAIT")
            return None

        results = compute_supertrend(candles, period, multiplier)

        if not results:
            db.set("st_health",    "STALE")
            db.set("st_direction", "NONE")
            utils.log(
                f"SuperTrend: not enough candles ({len(candles)} < {period + 1}). Waiting.",
                "WAIT"
            )
            return None

        latest = results[-1]

        db.set("st_direction",   latest["direction"])
        db.set("st_value",       str(latest["st_value"]))
        db.set("st_last_update", utils.fmt_time())
        db.set("st_health",      "OK")

        utils.log(
            f"SuperTrend [{period}/{multiplier}]: "
            f"{latest['direction']} | "
            f"Line=₹{latest['st_value']:,.2f} | "
            f"Candle Close=₹{latest['close']:,.2f}",
            "INFO"
        )
        return latest

    except Exception as e:
        utils.log(f"SuperTrend computation error: {e}", "ERROR")
        db.set("st_health",    "ERROR")
        db.set("st_direction", "NONE")
        return None


# ─────────────────────────────────────────────────────────────
# Health Watchdog
# ─────────────────────────────────────────────────────────────
def check_health() -> str:
    """
    Validates SuperTrend freshness.
    Returns 'OK', 'STALE', or 'ERROR'.
    STALE = last update was more than 15 minutes ago.
    """
    current         = db.get("st_health", "STALE")
    last_update_str = db.get("st_last_update", "")

    if last_update_str:
        try:
            import pytz
            from datetime import datetime
            IST         = pytz.timezone("Asia/Kolkata")
            last_update = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M:%S IST")
            last_update = IST.localize(last_update)
            age_minutes = (utils.ist_now() - last_update).total_seconds() / 60
            if age_minutes > 15:
                db.set("st_health", "STALE")
                utils.log(
                    f"ST WATCHDOG: Last update {age_minutes:.0f} min ago — STALE!",
                    "GUARD"
                )
                return "STALE"
        except Exception:
            pass

    return current


# ─────────────────────────────────────────────────────────────
# Signal helpers
# ─────────────────────────────────────────────────────────────
def direction_to_signal(direction: str) -> str:
    """BULLISH → CALL | BEARISH → PUT | anything else → NONE"""
    if direction == "BULLISH":
        return "CALL"
    elif direction == "BEARISH":
        return "PUT"
    return "NONE"


def detect_flip(new_direction: str, old_direction: str) -> bool:
    """True if direction flipped (BULLISH↔BEARISH). NONE does not count as flip."""
    if new_direction == "NONE" or old_direction == "NONE":
        return False
    return new_direction != old_direction
