"""
ULTIMATE STRATEGY TOURNAMENT: 8 Strategies Tested on 12 Months of BTC/ETH/SOL
==============================================================================
Testing SPOT + OPTIONS strategies from internet research:
1. OUR ADX FILTER (Baseline Champion)
2. RSI Mean Reversion (Buy RSI<30, Sell RSI>70) - SPOT
3. MACD Crossover - SPOT
4. Bollinger Band Squeeze Breakout - SPOT  
5. Triple EMA Crossover (8/21/55) - SPOT
6. RSI + MACD Combo Filter - SPOT
7. Supertrend + RSI Divergence Filter - OPTIONS (ATM)
8. HYBRID KING: ADX + RSI oversold confirmation - OPTIONS (ATM)

All SPOT strategies: Buy/Sell with full capital
All OPTIONS strategies: ATM, 3-Day expiry, Delta 0.55
"""

import sys, os
import pandas as pd
import numpy as np
import yfinance as yf

sys.path.append(os.getcwd())
import logic

CAPITAL = 5000.0
DELTA = 0.55
PREMIUM = 500.0
BROKERAGE = 2.0

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calc_bollinger(series, period=20, std_dev=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    return sma, upper, lower

def calc_adx(df, period=14):
    high = df['high']; low = df['low']; close = df['close']
    plus_dm = high.diff(); minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0; minus_dm[minus_dm < 0] = 0
    plus_dm[~(plus_dm > minus_dm)] = 0; minus_dm[~(minus_dm > plus_dm)] = 0
    tr1 = high - low; tr2 = (high - close.shift(1)).abs(); tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, min_periods=period, adjust=False).mean() / atr)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    return dx.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

def run_options_strategy(df, name, signal_func):
    trades = []
    current_pos = None
    entry_spot = 0.0
    for i in range(2, len(df)):
        signal = signal_func(df, i)
        if signal and signal != current_pos:
            if current_pos:
                exit_spot = float(df['close'].iloc[i])
                spot_move = exit_spot - entry_spot
                if "CE" in current_pos: pnl = round(spot_move * DELTA, 2)
                else: pnl = round(-spot_move * DELTA, 2)
                if pnl < -PREMIUM: pnl = -PREMIUM
                trades.append({"Exit Time": df.index[i], "Net P&L": round(pnl - 4, 2)})
            current_pos = signal
            entry_spot = float(df['close'].iloc[i])
    return trades

def run_spot_strategy(df, name, signal_func):
    trades = []
    current_pos = None
    entry_price = 0.0
    for i in range(2, len(df)):
        signal = signal_func(df, i)
        if signal and signal != current_pos:
            if current_pos:
                exit_price = float(df['close'].iloc[i])
                if current_pos == "LONG":
                    pct_return = ((exit_price - entry_price) / entry_price) * 100
                else:
                    pct_return = ((entry_price - exit_price) / entry_price) * 100
                pnl = round((pct_return / 100) * CAPITAL, 2)
                trades.append({"Exit Time": df.index[i], "Net P&L": round(pnl - 4, 2)})
            current_pos = signal
            entry_price = float(df['close'].iloc[i])
    return trades

def analyze(trades_list, name):
    if not trades_list: return None
    tdf = pd.DataFrame(trades_list)
    tdf['Exit Time'] = pd.to_datetime(tdf['Exit Time'])
    tdf['Month'] = tdf['Exit Time'].dt.to_period('M')
    monthly = tdf.groupby('Month')['Net P&L'].sum().reset_index()
    monthly['ROI %'] = round((monthly['Net P&L'] / CAPITAL) * 100, 2)
    equity = tdf['Net P&L'].cumsum()
    max_dd = (equity - equity.cummax()).min()
    total = tdf['Net P&L'].sum()
    pm = len(monthly[monthly['Net P&L'] > 0])
    is_loss = (tdf['Net P&L'] < 0).astype(int)
    streaks = is_loss * (is_loss.groupby((is_loss != is_loss.shift()).cumsum()).cumcount() + 1)
    return {
        "Strategy": name,
        "Trades": len(tdf),
        "Win%": round(len(tdf[tdf['Net P&L']>0])/len(tdf)*100,1),
        "P&L": round(total,2),
        "ROI%": round((total/CAPITAL)*100,1),
        "AvgMoROI%": round(monthly['ROI %'].mean(),2),
        "ProfMo": f"{pm}/{len(monthly)}",
        "MaxDD%": round((max_dd/CAPITAL)*100,1),
        "MaxLoss": int(streaks.max()),
        "Monthly": monthly
    }

# ========== FETCH DATA ==========
print("Downloading 12 months of 1H BTC data...")
df = yf.download("BTC-USD", period="365d", interval="1h", progress=False)
if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
df.columns = [str(c).lower() for c in df.columns]

# ========== INDICATORS ==========
print("Calculating all indicators...")
df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
df['adx'] = calc_adx(df, 14)
df['rsi'] = calc_rsi(df['close'], 14)
df['macd'], df['macd_signal'], df['macd_hist'] = calc_macd(df['close'])
df['bb_mid'], df['bb_upper'], df['bb_lower'] = calc_bollinger(df['close'], 20, 2)
df['ema_8'] = df['close'].ewm(span=8, adjust=False).mean()
df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
df['ema_55'] = df['close'].ewm(span=55, adjust=False).mean()

fast_dir = "SUPERTd_10_1.5"

# ========== 1. OUR ADX FILTER (OPTIONS) ==========
def sig_adx(df, i):
    if df['adx'].iloc[i] < 25: return None
    if df[fast_dir].iloc[i-1] == -1 and df[fast_dir].iloc[i] == 1: return "BUY CE"
    if df[fast_dir].iloc[i-1] == 1 and df[fast_dir].iloc[i] == -1: return "BUY PE"
    return None

# ========== 2. RSI MEAN REVERSION (SPOT) ==========
def sig_rsi(df, i):
    if df['rsi'].iloc[i-1] >= 30 and df['rsi'].iloc[i] < 30: return "LONG"
    if df['rsi'].iloc[i-1] <= 70 and df['rsi'].iloc[i] > 70: return "SHORT"
    return None

# ========== 3. MACD CROSSOVER (SPOT) ==========
def sig_macd(df, i):
    if df['macd'].iloc[i-1] < df['macd_signal'].iloc[i-1] and df['macd'].iloc[i] > df['macd_signal'].iloc[i]: return "LONG"
    if df['macd'].iloc[i-1] > df['macd_signal'].iloc[i-1] and df['macd'].iloc[i] < df['macd_signal'].iloc[i]: return "SHORT"
    return None

# ========== 4. BOLLINGER BREAKOUT (SPOT) ==========
def sig_bb(df, i):
    if df['close'].iloc[i-1] <= df['bb_upper'].iloc[i-1] and df['close'].iloc[i] > df['bb_upper'].iloc[i]: return "LONG"
    if df['close'].iloc[i-1] >= df['bb_lower'].iloc[i-1] and df['close'].iloc[i] < df['bb_lower'].iloc[i]: return "SHORT"
    return None

# ========== 5. TRIPLE EMA (SPOT) ==========
def sig_ema3(df, i):
    if df['ema_8'].iloc[i] > df['ema_21'].iloc[i] > df['ema_55'].iloc[i]:
        if df['ema_8'].iloc[i-1] <= df['ema_21'].iloc[i-1]: return "LONG"
    if df['ema_8'].iloc[i] < df['ema_21'].iloc[i] < df['ema_55'].iloc[i]:
        if df['ema_8'].iloc[i-1] >= df['ema_21'].iloc[i-1]: return "SHORT"
    return None

# ========== 6. RSI + MACD COMBO (SPOT) ==========
def sig_rsi_macd(df, i):
    macd_cross_up = df['macd'].iloc[i-1] < df['macd_signal'].iloc[i-1] and df['macd'].iloc[i] > df['macd_signal'].iloc[i]
    macd_cross_dn = df['macd'].iloc[i-1] > df['macd_signal'].iloc[i-1] and df['macd'].iloc[i] < df['macd_signal'].iloc[i]
    if macd_cross_up and df['rsi'].iloc[i] < 50: return "LONG"
    if macd_cross_dn and df['rsi'].iloc[i] > 50: return "SHORT"
    return None

# ========== 7. ST + RSI DIVERGENCE (OPTIONS) ==========
def sig_st_rsi(df, i):
    if df[fast_dir].iloc[i-1] == -1 and df[fast_dir].iloc[i] == 1 and df['rsi'].iloc[i] < 60: return "BUY CE"
    if df[fast_dir].iloc[i-1] == 1 and df[fast_dir].iloc[i] == -1 and df['rsi'].iloc[i] > 40: return "BUY PE"
    return None

# ========== 8. HYBRID KING: ADX + RSI (OPTIONS) ==========
def sig_hybrid(df, i):
    if df['adx'].iloc[i] < 25: return None
    if df[fast_dir].iloc[i-1] == -1 and df[fast_dir].iloc[i] == 1 and df['rsi'].iloc[i] < 65: return "BUY CE"
    if df[fast_dir].iloc[i-1] == 1 and df[fast_dir].iloc[i] == -1 and df['rsi'].iloc[i] > 35: return "BUY PE"
    return None

# ========== RUN ALL ==========
all_results = []

print("Testing 1. ADX Filter (OPTIONS)...")
all_results.append(analyze(run_options_strategy(df, "1", sig_adx), "1.ADX Filter (OPT)"))

print("Testing 2. RSI Mean Reversion (SPOT)...")
all_results.append(analyze(run_spot_strategy(df, "2", sig_rsi), "2.RSI Reversion (SPOT)"))

print("Testing 3. MACD Crossover (SPOT)...")
all_results.append(analyze(run_spot_strategy(df, "3", sig_macd), "3.MACD Cross (SPOT)"))

print("Testing 4. Bollinger Breakout (SPOT)...")
all_results.append(analyze(run_spot_strategy(df, "4", sig_bb), "4.Bollinger (SPOT)"))

print("Testing 5. Triple EMA (SPOT)...")
all_results.append(analyze(run_spot_strategy(df, "5", sig_ema3), "5.Triple EMA (SPOT)"))

print("Testing 6. RSI+MACD Combo (SPOT)...")
all_results.append(analyze(run_spot_strategy(df, "6", sig_rsi_macd), "6.RSI+MACD (SPOT)"))

print("Testing 7. ST+RSI Divergence (OPTIONS)...")
all_results.append(analyze(run_options_strategy(df, "7", sig_st_rsi), "7.ST+RSI (OPT)"))

print("Testing 8. HYBRID KING (OPTIONS)...")
all_results.append(analyze(run_options_strategy(df, "8", sig_hybrid), "8.HYBRID KING (OPT)"))

# ========== RESULTS ==========
all_results = [r for r in all_results if r is not None]

print("\n" + "=" * 110)
print("  ULTIMATE STRATEGY TOURNAMENT - 12 MONTHS BTC (Sorted by Annual ROI)")
print("=" * 110)

summary = pd.DataFrame([{k:v for k,v in r.items() if k != "Monthly"} for r in all_results])
summary = summary.sort_values(by="ROI%", ascending=False)
print(summary.to_string(index=False))

# Best strategy monthly breakdown
best = summary.iloc[0]['Strategy']
print(f"\n{'='*80}")
print(f"  MONTHLY BREAKDOWN: {best}")
print(f"{'='*80}")
best_data = [r for r in all_results if r['Strategy'] == best][0]['Monthly']
for _, row in best_data.iterrows():
    s = "[+]" if row['Net P&L'] > 0 else "[-]"
    print(f"  {s} {str(row['Month']):<10}  P&L: ${row['Net P&L']:>10,.2f}  ROI: {row['ROI %']:>8}%")
