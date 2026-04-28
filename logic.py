"""
logic.py - Supertrend Calculation (Pure Pandas/NumPy - No pandas_ta needed)
===========================================================================
Implements Supertrend from scratch so it works on ALL Python versions
including Python 3.14 on Streamlit Cloud.
"""

import pandas as pd
import numpy as np
import db


def calculate_supertrend(df, period=None, multiplier=None):
    """
    Calculates Supertrend indicator using pure pandas/numpy.
    No external dependencies like pandas_ta required.

    Supertrend Formula:
    - ATR = Average True Range over `period` candles
    - Basic Upper = (H+L)/2 + multiplier * ATR
    - Basic Lower = (H+L)/2 - multiplier * ATR
    - Final bands computed with trend-following logic
    - Direction: +1 = Bullish, -1 = Bearish
    """
    if period is None:
        period = int(float(db.get_param('st_period', 10)))
    if multiplier is None:
        multiplier = float(db.get_param('st_multiplier', 1.5))

    df = df.copy()

    high = df['high']
    low = df['low']
    close = df['close']

    # ── True Range
    hl  = high - low
    hc  = (high - close.shift(1)).abs()
    lc  = (low  - close.shift(1)).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)

    # ── ATR (Wilder's smoothing = EWM with alpha=1/period)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    # ── Basic Bands
    hl2 = (high + low) / 2
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    # ── Final Bands (trend-following adjustment)
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()

    for i in range(1, len(df)):
        prev_upper = final_upper.iloc[i - 1]
        prev_lower = final_lower.iloc[i - 1]
        prev_close = close.iloc[i - 1]

        # Upper band
        if basic_upper.iloc[i] < prev_upper or prev_close > prev_upper:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = prev_upper

        # Lower band
        if basic_lower.iloc[i] > prev_lower or prev_close < prev_lower:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = prev_lower

    # ── Direction
    direction = pd.Series(np.nan, index=df.index)
    supertrend = pd.Series(np.nan, index=df.index)

    for i in range(1, len(df)):
        prev_dir = direction.iloc[i - 1]

        if pd.isna(prev_dir):
            direction.iloc[i] = 1 if close.iloc[i] > final_upper.iloc[i] else -1
        elif prev_dir == 1:
            direction.iloc[i] = 1 if close.iloc[i] > final_lower.iloc[i] else -1
        else:
            direction.iloc[i] = -1 if close.iloc[i] < final_upper.iloc[i] else 1

        supertrend.iloc[i] = final_lower.iloc[i] if direction.iloc[i] == 1 else final_upper.iloc[i]

    # ── Attach to df using exact column names backtester expects
    col_prefix = f"SUPERT_{period}_{multiplier}"
    dir_col    = f"SUPERTd_{period}_{multiplier}"
    df[col_prefix] = supertrend
    df[dir_col]    = direction

    return df


def get_signal(df):
    """
    Detects a Supertrend FLIP on the last CLOSED candle.
    - Flip from -1 to +1 → BUY (CE)
    - Flip from +1 to -1 → SELL (PE)
    - No flip → WAIT
    """
    period     = int(float(db.get_param('st_period', 10)))
    multiplier = float(db.get_param('st_multiplier', 1.5))
    dir_col    = f"SUPERTd_{period}_{multiplier}"

    if dir_col not in df.columns:
        return "WAIT"

    try:
        last_dir = df[dir_col].iloc[-2]   # Last CLOSED candle
        prev_dir = df[dir_col].iloc[-3]   # Candle before that

        if prev_dir == -1 and last_dir == 1:
            return "BUY"
        elif prev_dir == 1 and last_dir == -1:
            return "SELL"
    except Exception as e:
        print(f"[Logic] Signal Error: {e}")

    return "WAIT"
