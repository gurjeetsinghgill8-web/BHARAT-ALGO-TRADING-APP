"""
nifty_logic.py — BHARAT ALGOVERSE v3.0 | Nifty Module
=======================================================
LEGO BLOCK: Signal Engine for NSE Nifty 50 / Stocks
• Supertrend (TradingView-exact, same maths as crypto engine)
• Multi-timeframe: 5m, 15m, 30m, 1h, 1d
• Multi-setting: configurable Period & Multiplier from DB
• Data source: yfinance (NSE free data) - no paid feed needed
• Uses iloc[-2] (last CLOSED candle) to prevent signal flicker
• Completely isolated — does NOT touch crypto code or DB keys
"""

import pandas as pd
import numpy as np
import yfinance as yf
import db
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

# ── yfinance interval→period lookup ────────────────────────
_YF_PERIOD = {
    '5m':  '5d',
    '15m': '5d',
    '30m': '5d',
    '1h':  '30d',
    '1d':  '1y',
}

# ============================================================
# LEGO 1: Supertrend Calculator (TradingView Pine V5 exact)
# ============================================================
def calculate_supertrend(df: pd.DataFrame, period: int = None,
                         multiplier: float = None) -> pd.DataFrame:
    if period is None:
        period = int(float(db.get_param('nifty_st_period', '10') or '10'))
    if multiplier is None:
        multiplier = float(db.get_param('nifty_st_multiplier', '1.5') or '1.5')

    df = df.copy()
    high  = df['high']
    low   = df['low']
    close = df['close']

    hl  = high - low
    hc  = (high - close.shift(1)).abs()
    lc  = (low  - close.shift(1)).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    hl2         = (high + low) / 2
    basic_upper = (hl2 + multiplier * atr).fillna(0)
    basic_lower = (hl2 - multiplier * atr).fillna(0)

    n = len(df)
    fu = np.zeros(n)
    fl = np.zeros(n)
    sv = np.zeros(n)
    sd = np.ones(n)

    for i in range(n):
        if i == 0 or basic_upper.iloc[i] == 0:
            fu[i] = basic_upper.iloc[i]
            fl[i] = basic_lower.iloc[i]
            sv[i] = fu[i]
            sd[i] = -1
            continue

        fu[i] = basic_upper.iloc[i] if (basic_upper.iloc[i] < fu[i-1] or
                                         close.iloc[i-1] > fu[i-1]) else fu[i-1]
        fl[i] = basic_lower.iloc[i] if (basic_lower.iloc[i] > fl[i-1] or
                                         close.iloc[i-1] < fl[i-1]) else fl[i-1]

        if sd[i-1] == 1:
            sd[i], sv[i] = (1, fl[i]) if close.iloc[i] > fl[i] else (-1, fu[i])
        else:
            sd[i], sv[i] = (-1, fu[i]) if close.iloc[i] < fu[i] else (1, fl[i])

    df['sar']    = sv
    df['st_dir'] = sd   # 1 = bullish, -1 = bearish
    return df


# ============================================================
# LEGO 2: NSE Candle Fetcher (yfinance)
# ============================================================
def fetch_nifty_candles(symbol: str = "^NSEI", timeframe: str = "15m",
                        limit: int = 120) -> tuple:
    """Returns (DataFrame, error_string). Always ascending by time."""
    try:
        period = _YF_PERIOD.get(timeframe, '5d')
        df = yf.Ticker(symbol).history(period=period, interval=timeframe,
                                        auto_adjust=True)
        if df is None or df.empty:
            return pd.DataFrame(), f"No yfinance data for {symbol}/{timeframe}"

        df = df.rename(columns={'Open':'open','High':'high','Low':'low',
                                 'Close':'close','Volume':'volume'})
        if df.index.tz is not None:
            df.index = df.index.tz_convert(IST)
        df['time'] = df.index
        df = df.reset_index(drop=True)

        if len(df) > limit:
            df = df.tail(limit).reset_index(drop=True)

        for col in ['open','high','low','close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        return df.dropna(subset=['open','high','low','close']).reset_index(drop=True), ""

    except Exception as e:
        return pd.DataFrame(), str(e)


# ============================================================
# LEGO 3: Signal Engine
# ============================================================
def get_nifty_signal(symbol: str = None, timeframe: str = None,
                     period: int = None, multiplier: float = None) -> str:
    """Returns 'BUY' | 'SELL' | 'WAIT'. Uses last closed candle."""
    if symbol is None:
        symbol = db.get_param('nifty_symbol', '^NSEI') or '^NSEI'
    if timeframe is None:
        timeframe = db.get_param('nifty_timeframe', '15m') or '15m'

    df, err = fetch_nifty_candles(symbol, timeframe)
    if df.empty or len(df) < 3:
        print(f"[NIFTY] No candles: {err}")
        return "WAIT"

    df = calculate_supertrend(df, period=period, multiplier=multiplier)
    last = df.iloc[-2]   # last CLOSED candle

    if last['close'] > last['sar']:
        return "BUY"
    elif last['close'] < last['sar']:
        return "SELL"
    return "WAIT"


# ============================================================
# LEGO 4: Market Hours Guard
# ============================================================
def is_market_open() -> bool:
    """True only 9:25 AM – 3:10 PM IST, Mon–Fri."""
    now = datetime.now(IST)
    if now.weekday() > 4:
        return False
    o = now.replace(hour=9,  minute=25, second=0, microsecond=0)
    c = now.replace(hour=15, minute=10, second=0, microsecond=0)
    return o <= now <= c


def time_to_open_str() -> str:
    """Human-readable countdown to next market open."""
    now  = datetime.now(IST)
    o    = now.replace(hour=9, minute=25, second=0, microsecond=0)
    import pandas as _pd
    if now < o and now.weekday() <= 4:
        delta = o - now
    else:
        d = 1
        while True:
            cand = (now + _pd.Timedelta(days=d)).replace(
                hour=9, minute=25, second=0, microsecond=0)
            if cand.weekday() <= 4:
                delta = cand - now
                break
            d += 1
    h, r = divmod(int(delta.total_seconds()), 3600)
    m, _ = divmod(r, 60)
    return f"{h}h {m}m"
