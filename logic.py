"""
logic.py - Industry-Standard Supertrend (Pure Python/Pandas)
===========================================================
Re-implemented to match TradingView/Pine Script exactly.
Fixes the "Whipsaw" bug where bands were updating incorrectly.
"""

import pandas as pd
import numpy as np
import db

def calculate_supertrend(df, period=None, multiplier=None):
    if period is None:
        period = int(float(db.get_param('st_period', 10)))
    if multiplier is None:
        multiplier = float(db.get_param('st_multiplier', 1.5))

    df = df.copy()
    
    # 1. Calculate ATR (Standard Wilder's)
    high = df['high']
    low = df['low']
    close = df['close']
    
    hl = high - low
    hc = (high - close.shift(1)).abs()
    lc = (low - close.shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean() # Simple Moving Average for ATR in many ST versions
    # Note: Some use EWM for ATR. Standard TradingView uses RMA (Wilder's).
    # Let's use RMA style (EWM with alpha=1/period) for better smoothness.
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    # 2. Basic Upper and Lower Bands
    hl2 = (high + low) / 2
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)

    # 3. Final Upper and Lower Bands
    # Logic: Lower band only moves UP, Upper band only moves DOWN
    final_upper = [0.0] * len(df)
    final_lower = [0.0] * len(df)
    
    for i in range(len(df)):
        if i == 0:
            final_upper[i] = basic_upper.iloc[i]
            final_lower[i] = basic_lower.iloc[i]
        else:
            # Upper Band logic
            if basic_upper.iloc[i] < final_upper[i-1] or close.iloc[i-1] > final_upper[i-1]:
                final_upper[i] = basic_upper.iloc[i]
            else:
                final_upper[i] = final_upper[i-1]
                
            # Lower Band logic
            if basic_lower.iloc[i] > final_lower[i-1] or close.iloc[i-1] < final_lower[i-1]:
                final_lower[i] = basic_lower.iloc[i]
            else:
                final_lower[i] = final_lower[i-1]

    # 4. Supertrend Trend and Values
    st_values = [0.0] * len(df)
    st_dir = [1] * len(df) # 1 = Bull, -1 = Bear
    
    for i in range(len(df)):
        if i == 0:
            st_values[i] = final_upper[i]
            st_dir[i] = -1
        else:
            if st_dir[i-1] == 1:
                if close.iloc[i] > final_lower[i]:
                    st_dir[i] = 1
                    st_values[i] = final_lower[i]
                else:
                    st_dir[i] = -1
                    st_values[i] = final_upper[i]
            else:
                if close.iloc[i] < final_upper[i]:
                    st_dir[i] = -1
                    st_values[i] = final_upper[i]
                else:
                    st_dir[i] = 1
                    st_values[i] = final_lower[i]

    col_prefix = f"SUPERT_{period}_{multiplier}"
    dir_col    = f"SUPERTd_{period}_{multiplier}"
    
    df[col_prefix] = st_values
    df[dir_col]    = st_dir
    
    return df

def get_signal(df):
    period     = int(float(db.get_param('st_period', 10)))
    multiplier = float(db.get_param('st_multiplier', 1.5))
    dir_col    = f"SUPERTd_{period}_{multiplier}"

    if dir_col not in df.columns: return "WAIT"

    try:
        # Check for crossover
        last_dir = df[dir_col].iloc[-2]
        prev_dir = df[dir_col].iloc[-3]

        if prev_dir == -1 and last_dir == 1: return "BUY"
        if prev_dir == 1 and last_dir == -1: return "SELL"
    except:
        pass
    return "WAIT"
