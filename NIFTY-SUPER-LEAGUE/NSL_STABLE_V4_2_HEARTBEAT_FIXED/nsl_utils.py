"""
nsl_utils.py — NIFTY SUPER LEAGUE | LEGO 2: Utilities
=======================================================
IST time helpers, market open check, timestamped logging,
seconds-to-next-5-min-candle calculation.
NO external dependencies beyond stdlib + pytz.

MARKET HOURS: 9:16 AM open | 3:00 PM force close (3:10 PM market window end).
"""

import sys
import datetime
import pytz

# Force UTF-8 output on Windows to prevent emoji crash
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import os
import socket as _socket

import nsl_config as cfg

# ── Force IPv4 only ── prevents Upstox UDAPI1154 error ───────
# Ensures ALL requests use IPv4 — matches the static VPN IP.
try:
    import urllib3.util.connection as _urllib3_conn
    _urllib3_conn.HAS_IPV6 = False
except Exception:
    pass

_orig_getaddrinfo = _socket.getaddrinfo
def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    results = _orig_getaddrinfo(host, port, family, type, proto, flags)
    ipv4 = [r for r in results if r[0] == _socket.AF_INET]
    return ipv4 if ipv4 else results
_socket.getaddrinfo = _ipv4_getaddrinfo
# ─────────────────────────────────────────────────────────────

IST      = pytz.timezone("Asia/Kolkata")
LOG_FILE = "nsl_engine.log"


# ─────────────────────────────────────────────────────────────
# Time helpers
# ─────────────────────────────────────────────────────────────
def ist_now() -> datetime.datetime:
    """Returns current time in IST (timezone-aware)."""
    return datetime.datetime.now(IST)


def ist_today() -> datetime.date:
    return ist_now().date()


def is_weekday() -> bool:
    return ist_now().weekday() < 5  # Mon=0 … Fri=4


def is_market_open() -> bool:
    """True if current IST time is within 09:20–15:10 on a weekday."""
    if not is_weekday():
        return False
    now      = ist_now()
    open_dt  = now.replace(hour=cfg.MARKET_OPEN_H,  minute=cfg.MARKET_OPEN_M,  second=0, microsecond=0)
    close_dt = now.replace(hour=cfg.MARKET_CLOSE_H, minute=cfg.MARKET_CLOSE_M, second=0, microsecond=0)
    return open_dt <= now <= close_dt


def is_squareoff_time() -> bool:
    """True if it's time to force-close all positions (3:00 PM IST)."""
    now  = ist_now()
    sq_h = getattr(cfg, 'SQUAREOFF_H', cfg.MARKET_CLOSE_H)
    sq_m = getattr(cfg, 'SQUAREOFF_M', cfg.MARKET_CLOSE_M)
    return (
        now.hour > sq_h or
        (now.hour == sq_h and now.minute >= sq_m)
    )


def is_heartbeat_window() -> bool:
    """
    True if current IST time is within the HEARTBEAT window:
    09:15:00 AM → 15:00:00 PM on weekdays.

    This is DIFFERENT from is_market_open() (which is 09:20–15:10).
    Heartbeat starts at 9:15 (first candle of day) and ends at 3:00 PM
    (force-close time). Every 5-min candle boundary in this window
    gets exactly one heartbeat.
    """
    if not is_weekday():
        return False
    now      = ist_now()
    # Window: 09:15:00 to 15:00:59
    start_ok = (now.hour > 9) or (now.hour == 9 and now.minute >= 15)
    end_ok   = (now.hour < 15) or (now.hour == 15 and now.minute == 0)
    return start_ok and end_ok


def seconds_to_next_5min_candle() -> int:
    """
    Returns seconds until the next candle boundary based on cfg.ST_CANDLE_MINUTES.
    1-min mode: fires every ~60 seconds.
    5-min mode: fires every ~300 seconds.
    Adds 3 seconds buffer so candle is fully closed.
    """
    candle_minutes    = getattr(cfg, 'ST_CANDLE_MINUTES', 5)
    now               = ist_now()
    elapsed_in_period = (now.minute % candle_minutes) * 60 + now.second
    seconds_left      = (candle_minutes * 60) - elapsed_in_period + 3  # +3s buffer
    return max(seconds_left, 3)



def fmt_time(dt: datetime.datetime = None) -> str:
    """Human-readable IST timestamp string."""
    if dt is None:
        dt = ist_now()
    return dt.strftime("%Y-%m-%d %H:%M:%S IST")


# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────
LEVEL_ICONS = {
    "INFO":  "",
    "TRADE": "[TRADE]",
    "ALERT": "[ALERT]",
    "ERROR": "[ERROR]",
    "OK":    "[OK]",
    "WAIT":  "[WAIT]",
    "GUARD": "[GUARD]",
}

def log(msg: str, level: str = "INFO") -> None:
    """Timestamped terminal + file log."""
    ts   = fmt_time()
    icon = LEVEL_ICONS.get(level.upper(), "")
    line = f"[{ts}] [{level.upper()}] {icon} {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    # Print to terminal only when not running under systemd
    if not os.environ.get("INVOCATION_ID"):
        print(line)
