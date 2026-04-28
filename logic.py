"""
logic.py - Ultra-Stable Supertrend
==================================
Matches TradingView Pine Script V5 exactly.
Uses RMA (Wilder's) for ATR.
"""

import pandas as pd
import numpy as np
import db

def calculate_supertrend(df, period=None, multiplier=None):
    if period is None:
        period = int(float(db.get_param('st_period', 10)))
    if multiplier is None:
        multiplier = float(db.get_param('st_multiplier', 1.0))

    df = df.copy()
    
    # Standard OHLC
    high = df['high']
    low = df['low']
    close = df['close']
    
    # 1. TR and ATR (Wilder's Smoothing / RMA)
    hl = high - low
    hc = (high - close.shift(1)).abs()
    lc = (low - close.shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    
    # RMA = EWM with alpha = 1/period
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    # 2. Basic Bands
    hl2 = (high + low) / 2
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)

    # 3. Final Bands and Direction (Combined Loop to ensure consistency)
    final_upper = np.zeros(len(df))
    final_lower = np.zeros(len(df))
    st_values = np.zeros(len(df))
    st_dir = np.ones(len(df)) # 1 = Bull, -1 = Bear
    
    for i in range(len(df)):
        if i == 0:
            final_upper[i] = basic_upper.iloc[i]
            final_lower[i] = basic_lower.iloc[i]
            st_values[i] = final_upper[i]
            st_dir[i] = -1
            continue
            
        # Update Final Upper Band
        if basic_upper.iloc[i] < final_upper[i-1] or close.iloc[i-1] > final_upper[i-1]:
            final_upper[i] = basic_upper.iloc[i]
        else:
            final_upper[i] = final_upper[i-1]
            
        # Update Final Lower Band
        if basic_lower.iloc[i] > final_lower[i-1] or close.iloc[i-1] < final_lower[i-1]:
            final_lower[i] = basic_lower.iloc[i]
        else:
            final_lower[i] = final_lower[i-1]
            
        # Determine Direction
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
    multiplier = float(db.get_param('st_multiplier', 1.0))
    dir_col    = f"SUPERTd_{period}_{multiplier}"

    if dir_col not in df.columns: return "WAIT"

    try:
        # Detect actual crossover
        last_dir = df[dir_col].iloc[-2]
        prev_dir = df[dir_col].iloc[-3]

        if prev_dir == -1 and last_dir == 1: return "BUY"
        if prev_dir == 1 and last_dir == -1: return "SELL"
    except:
        pass
    return "WAIT"
