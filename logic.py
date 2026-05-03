"""
logic.py - HYBRID KING Engine
==============================
Supertrend (TradingView-exact) + ADX + RSI
All indicators built in pure Python/Pandas.
"""

import pandas as pd
import numpy as np
import db

# ============================================================
# SUPERTREND (Matches TradingView Pine Script V5)
# ============================================================
def calculate_supertrend(df, period=None, multiplier=None):
    if period is None:
        period = int(float(db.get_param('st_period', 10)))
    if multiplier is None:
        multiplier = float(db.get_param('st_multiplier', 1.5))

    df = df.copy()
    high = df['high']
    low = df['low']
    close = df['close']
    
    # TR and ATR (Wilder's RMA)
    hl = high - low
    hc = (high - close.shift(1)).abs()
    lc = (low - close.shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    # Basic Bands
    hl2 = (high + low) / 2
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)

    # Final Bands + Direction (single loop)
    final_upper = np.zeros(len(df))
    final_lower = np.zeros(len(df))
    st_values = np.zeros(len(df))
    st_dir = np.ones(len(df))
    
    basic_upper = basic_upper.fillna(0)
    basic_lower = basic_lower.fillna(0)
    
    for i in range(len(df)):
        if i == 0 or basic_upper.iloc[i] == 0:
            final_upper[i] = basic_upper.iloc[i]
            final_lower[i] = basic_lower.iloc[i]
            st_values[i] = final_upper[i]
            st_dir[i] = -1
            continue
            
        if basic_upper.iloc[i] < final_upper[i-1] or close.iloc[i-1] > final_upper[i-1]:
            final_upper[i] = basic_upper.iloc[i]
        else:
            final_upper[i] = final_upper[i-1]
            
        if basic_lower.iloc[i] > final_lower[i-1] or close.iloc[i-1] < final_lower[i-1]:
            final_lower[i] = basic_lower.iloc[i]
        else:
            final_lower[i] = final_lower[i-1]
            
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
    df['sar']      = st_values # Alias for easier access
    return df

# ============================================================
# RSI (Wilder's Smoothing)
# ============================================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ============================================================
# ADX (Average Directional Index)
# ============================================================
def calculate_adx(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_dm[~(plus_dm > minus_dm)] = 0
    minus_dm[~(minus_dm > plus_dm)] = 0
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    df[f'ADX_{period}'] = adx
    df['adx'] = adx # Alias
    return df

# ============================================================
# LEGO BLOCK 1: Whipsaw Protection (Signal Logic)
# ============================================================
def get_signal(df):
    """
    Whipsaw Protection: Uses iloc[-2] to look at the last completed candle only.
    Return 'BUY' if close > sar, and 'SELL' if close < sar.
    """
    if 'sar' not in df.columns:
        return "WAIT"
        
    # iloc[-2] ensures we look at the closed candle, not the live fluctuating one
    latest = df.iloc[-2]
    
    if latest['close'] > latest['sar']:
        return "BUY"
    elif latest['close'] < latest['sar']:
        return "SELL"
    
    return "WAIT"

# SUPREME CLOUD SYNC: 2026-05-03
