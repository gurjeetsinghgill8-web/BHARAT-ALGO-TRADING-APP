"""
nsl_data.py — NIFTY SUPER LEAGUE | LEGO 4: Data Feed
======================================================
Fetches:
  - Nifty 50 spot LTP from Upstox (always live, DB fallback on failure)
  - 5-minute historical candles (built from 1-min intraday candles)
  - Candle guard: only act on each closed candle ONCE

CRITICAL RULES:
  1. get_nifty_spot_ltp() always hits the API first.
     If API fails → returns last known DB value (never returns 0 silently).
  2. get_candles_for_supertrend() returns candles[:-1] — NEVER the forming candle.
  3. Minimum ST_MIN_CANDLES closed candles required for a valid signal.
"""

import requests
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

import nsl_db as db
import nsl_config as cfg
import nsl_utils as utils


def _headers() -> dict:
    token = db.get("upstox_access_token", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


# ─────────────────────────────────────────────────────────────
# Nifty 50 Spot LTP
# ─────────────────────────────────────────────────────────────
def get_nifty_spot_ltp() -> float:
    """
    Returns Nifty 50 spot price from Upstox.
    Always hits API first.
    On failure: returns last known DB value so dashboard never shows 0.
    Updates DB current_ltp as side effect.
    """
    try:
        url    = f"{cfg.UPSTOX_BASE}/market-quote/quotes"
        params = {"instrument_key": cfg.NIFTY_INST_KEY}
        resp   = requests.get(url, headers=_headers(), params=params,
                              timeout=8, proxies=db.get_proxy())

        if resp.status_code == 200:
            data = resp.json().get("data", {})
            for key, val in data.items():
                if "nifty" in key.lower() and "50" in key.lower():
                    ltp = float(val.get("last_price", 0) or val.get("ltp", 0) or 0)
                    if ltp > 0:
                        db.set("current_ltp", str(ltp))
                        return ltp

        utils.log(f"Spot LTP API failed: {resp.status_code}. Using last known value.", "WAIT")

    except Exception as e:
        utils.log(f"get_nifty_spot_ltp exception: {e}. Using last known value.", "WAIT")

    # Fallback: return last known DB value (never return 0 silently)
    fallback = float(db.get("current_ltp", "0") or "0")
    if fallback > 0:
        utils.log(f"Spot LTP fallback from DB: ₹{fallback:,.2f}", "WAIT")
    return fallback


# ─────────────────────────────────────────────────────────────
# 5-Minute Historical Candles
# ─────────────────────────────────────────────────────────────
def get_nifty_candles(n: int = 30) -> list[dict]:
    """
    Fetches candles from Upstox for the configured interval.
    In 1-minute mode: returns raw 1-min candles.
    In 5-minute mode: fetches 1-min and groups into 5-min bars.
    Returns list sorted oldest->newest.
    """
    candle_minutes = getattr(cfg, 'ST_CANDLE_MINUTES', 5)

    try:
        url = (
            f"{cfg.UPSTOX_BASE}/historical-candle/intraday/"
            f"{requests.utils.quote(cfg.NIFTY_INST_KEY, safe='')}/1minute"
        )
        resp = requests.get(url, headers=_headers(), timeout=10,
                            proxies=db.get_proxy())

        if resp.status_code != 200:
            utils.log(f"Candle fetch failed: {resp.status_code} {resp.text[:100]}", "ERROR")
            return []

        raw = resp.json().get("data", {}).get("candles", [])
        if not raw:
            utils.log("Candle response empty.", "WAIT")
            return []

        # Parse 1-min candles
        one_min = []
        for c in raw:
            if len(c) >= 5:
                one_min.append({
                    "timestamp": c[0],
                    "open":      float(c[1]),
                    "high":      float(c[2]),
                    "low":       float(c[3]),
                    "close":     float(c[4]),
                    "volume":    int(c[5]) if len(c) > 5 else 0,
                })
        one_min.sort(key=lambda x: x["timestamp"])

        if candle_minutes <= 1:
            # 1-minute mode: return raw candles directly
            result = one_min[-n:] if len(one_min) >= n else one_min
            return result

        # 5-minute mode: group 1-min into N-min bars
        buckets = defaultdict(list)
        for bar in one_min:
            ts_str = bar["timestamp"]
            try:
                ts_clean    = ts_str[:16]
                ts_dt       = datetime.strptime(ts_clean, "%Y-%m-%dT%H:%M")
                floored_min = (ts_dt.minute // candle_minutes) * candle_minutes
                bucket_key  = ts_dt.replace(minute=floored_min, second=0)
            except Exception:
                bucket_key = ts_str[:14]
            buckets[bucket_key].append(bar)

        grouped = []
        for bucket_ts in sorted(buckets.keys()):
            bars = buckets[bucket_ts]
            grouped.append({
                "timestamp": bars[0]["timestamp"],
                "open":      bars[0]["open"],
                "high":      max(b["high"]  for b in bars),
                "low":       min(b["low"]   for b in bars),
                "close":     bars[-1]["close"],
                "volume":    sum(b["volume"] for b in bars),
            })

        result = grouped[-n:] if len(grouped) >= n else grouped
        return result

    except Exception as e:
        utils.log(f"get_nifty_candles exception: {e}", "ERROR")
        return []


# Keep old name as alias for compatibility
def get_nifty_5min_candles(n: int = 30) -> list[dict]:
    return get_nifty_candles(n=n)


# ───────────────────────────────────────────────────────────────
# Yesterday's 5-min candles (ST warmup at market open)
# ───────────────────────────────────────────────────────────────
def _get_yesterday_5min_candles() -> list[dict]:
    """
    Fetches previous trading day's 1-min candles from Upstox historical API,
    then groups them into 5-min bars. Used ONLY to pre-warm SuperTrend at
    market open so engine doesn't wait 60 minutes.
    Note: Upstox historical API only supports 1minute interval (not 5minute).
    Skips weekends automatically.
    """
    today    = utils.ist_today()
    prev_day = today - timedelta(days=1)
    while prev_day.weekday() >= 5:   # 5=Sat, 6=Sun
        prev_day -= timedelta(days=1)
    prev_str = prev_day.strftime("%Y-%m-%d")

    try:
        encoded_key = requests.utils.quote(cfg.NIFTY_INST_KEY, safe='')
        # Historical API: only 1minute interval supported for intraday history
        url  = (
            f"{cfg.UPSTOX_BASE}/historical-candle/"
            f"{encoded_key}/1minute/{prev_str}/{prev_str}"
        )
        resp = requests.get(url, headers=_headers(), timeout=12,
                            proxies=db.get_proxy())

        if resp.status_code != 200:
            utils.log(f"Yesterday 1min fetch failed: {resp.status_code} {resp.text[:100]}", "WAIT")
            return []

        raw = resp.json().get("data", {}).get("candles", [])
        if not raw:
            utils.log(f"Yesterday candles: empty for {prev_str}", "WAIT")
            return []

        # Parse 1-min candles
        one_min = []
        for c in raw:
            if len(c) >= 5:
                one_min.append({
                    "timestamp": c[0],
                    "open":      float(c[1]),
                    "high":      float(c[2]),
                    "low":       float(c[3]),
                    "close":     float(c[4]),
                    "volume":    int(c[5]) if len(c) > 5 else 0,
                })
        one_min.sort(key=lambda x: x["timestamp"])

        # Group into 5-min bars (same logic as get_nifty_candles)
        from collections import defaultdict as _dd
        candle_minutes = getattr(cfg, 'ST_CANDLE_MINUTES', 5)
        buckets = _dd(list)
        for bar in one_min:
            ts_str = bar["timestamp"]
            try:
                ts_clean    = ts_str[:16]
                ts_dt       = datetime.strptime(ts_clean, "%Y-%m-%dT%H:%M")
                floored_min = (ts_dt.minute // candle_minutes) * candle_minutes
                bucket_key  = ts_dt.replace(minute=floored_min, second=0)
            except Exception:
                bucket_key = ts_str[:14]
            buckets[bucket_key].append(bar)

        grouped = []
        for bucket_ts in sorted(buckets.keys()):
            bars = buckets[bucket_ts]
            grouped.append({
                "timestamp": bars[0]["timestamp"],
                "open":      bars[0]["open"],
                "high":      max(b["high"]  for b in bars),
                "low":       min(b["low"]   for b in bars),
                "close":     bars[-1]["close"],
                "volume":    sum(b["volume"] for b in bars),
            })

        utils.log(
            f"Yesterday ({prev_str}): {len(one_min)} 1-min → {len(grouped)} 5-min candles for ST warmup.",
            "INFO"
        )
        return grouped

    except Exception as e:
        utils.log(f"_get_yesterday_5min_candles exception: {e}", "WAIT")
        return []


# ─────────────────────────────────────────────────────────────
# Closed Candles for SuperTrend (SAFE — never forming candle)
# ─────────────────────────────────────────────────────────────
def get_candles_for_supertrend() -> list[dict]:
    """
    Returns FULLY CLOSED candles for SuperTrend computation.
    Uses cfg.ST_CANDLE_MINUTES to determine timeframe (1-min or 5-min).
    RULE: Always drops candles[-1] (the current forming/unstable candle).
    If today's candles < ST_MIN_CANDLES (market just opened), prepends
    yesterday's 5-min candles so SuperTrend is warm from first cycle.
    """
    candle_minutes = getattr(cfg, 'ST_CANDLE_MINUTES', 5)
    candles = get_nifty_candles(n=60)

    if len(candles) < 2:
        utils.log(f"Not enough {candle_minutes}-min candles fetched. Waiting.", "WAIT")
        return []

    # Drop the last (forming) candle — it is NEVER stable
    closed = candles[:-1]

    utils.log(
        f"Candles [{candle_minutes}min]: {len(candles)} fetched | {len(closed)} closed",
        "INFO"
    )

    if len(closed) < cfg.ST_MIN_CANDLES:
        # Not enough today — fetch yesterday's candles to warm up SuperTrend
        utils.log(
            f"Only {len(closed)} closed candles — need {cfg.ST_MIN_CANDLES}. "
            f"Fetching yesterday's data for ST warmup...",
            "WAIT"
        )
        yesterday = _get_yesterday_5min_candles()
        if yesterday:
            # Take enough from yesterday to fill the gap (with +5 buffer)
            needed = cfg.ST_MIN_CANDLES - len(closed) + 5
            padded = yesterday[-needed:] + closed
            utils.log(
                f"ST Warmup: {len(yesterday[-needed:])} yesterday + "
                f"{len(closed)} today = {len(padded)} candles. Ready!",
                "INFO"
            )
            return padded
        else:
            utils.log(
                f"Yesterday candles unavailable. Waiting for today's warmup "
                f"({len(closed)}/{cfg.ST_MIN_CANDLES}).",
                "WAIT"
            )
            return []

    return closed


# ─────────────────────────────────────────────────────────────
# Candle Guard helpers
# ─────────────────────────────────────────────────────────────
def is_new_candle(previous_candle: dict) -> bool:
    """
    True if the previous_candle timestamp differs from the last
    recorded candle in DB. Prevents acting on same candle twice.
    """
    if not previous_candle:
        return False
    ts          = str(previous_candle["timestamp"])
    last_stored = db.get("last_candle_time", "")
    return ts != last_stored


def record_candle_time(previous_candle: dict) -> None:
    """Stamps the candle timestamp so it is not acted on again."""
    if previous_candle:
        db.set("last_candle_time", str(previous_candle["timestamp"]))


# ─────────────────────────────────────────────────────────────
# Option LTP — always live when trade is active
# ─────────────────────────────────────────────────────────────
def get_option_ltp(instrument_key: str) -> float:
    """
    Returns the current LTP of the held option contract.
    v4.1: Retries 3 times (2s gap) before failing.
    On 3 failures: sets ltp_fetch_failed=YES flag for Self-Healing Agent.
    Updates DB current_option_ltp as side effect.
    """
    if not instrument_key or instrument_key == "NONE":
        return 0.0

    for attempt in range(1, 4):
        try:
            url    = f"{cfg.UPSTOX_BASE}/market-quote/quotes"
            params = {"instrument_key": instrument_key}
            resp   = requests.get(url, headers=_headers(), params=params,
                                  timeout=8, proxies=db.get_proxy())

            if resp.status_code == 200:
                data = resp.json().get("data", {})
                for key, val in data.items():
                    ltp = float(val.get("last_price", 0) or val.get("ltp", 0) or 0)
                    if ltp > 0:
                        db.set("current_option_ltp", str(ltp))
                        db.set("ltp_fetch_failed", "NO")
                        return ltp

            utils.log(f"Option LTP attempt {attempt}/3 failed: {resp.status_code}.", "WAIT")

        except Exception as e:
            utils.log(f"get_option_ltp attempt {attempt}/3 exception: {e}", "WAIT")

        if attempt < 3:
            time.sleep(2)

    # All 3 attempts failed
    utils.log("Option LTP: All 3 attempts failed. Self-Healing Agent will act.", "ALERT")
    db.set("ltp_fetch_failed", "YES")
    fallback = float(db.get("current_option_ltp", "0") or "0")
    return fallback
