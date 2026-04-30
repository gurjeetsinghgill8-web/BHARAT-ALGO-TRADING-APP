"""
DEEP STRATEGY RESEARCH: Finding the lowest drawdown, most consistent BTC strategy.
===================================================================================
Strategies Tested:
1. BASELINE: Plain Supertrend (1H, 10, 1.5) - Our current best
2. DUAL SUPERTREND: Only trade when BOTH a fast (10,1.5) AND slow (20,3.0) agree
3. EMA TREND FILTER: Only BUY CE when price > 50 EMA, only BUY PE when price < 50 EMA
4. ADX FILTER: Only trade when ADX > 25 (strong trend), skip ranging markets
5. COMBINED FORTRESS: Dual ST + EMA + ADX all must agree (Maximum safety)

For each strategy, we measure:
- Total Annual P&L
- Max Drawdown (worst peak-to-trough)
- % of Profitable Months
- Average Monthly ROI
- Max Losing Streak (consecutive losing trades)
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

def fetch_data():
    print("Downloading 12 months of 1H BTC data...")
    df = yf.download("BTC-USD", period="365d", interval="1h", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    return df

def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_adx(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    # Where +DM > -DM, keep +DM, else 0
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
    return adx

def run_strategy(df, strategy_name, signal_func):
    """Generic engine: takes a signal function and runs the backtest."""
    trades = []
    current_pos = None
    entry_spot = 0.0
    entry_time = None
    
    for i in range(2, len(df)):
        signal = signal_func(df, i)
        
        if signal and signal != current_pos:
            if current_pos:
                exit_spot = round(float(df['close'].iloc[i]), 2)
                spot_move = exit_spot - entry_spot
                
                if "CE" in current_pos:
                    realized_pnl = round(spot_move * DELTA, 2)
                else:
                    realized_pnl = round(-spot_move * DELTA, 2)
                
                if realized_pnl < -PREMIUM: realized_pnl = -PREMIUM
                net_pnl = round(realized_pnl - (BROKERAGE * 2), 2)
                
                trades.append({
                    "Exit Time": df.index[i],
                    "Type": current_pos,
                    "Entry Spot": entry_spot,
                    "Exit Spot": exit_spot,
                    "Net P&L": net_pnl
                })
            
            current_pos = signal
            entry_spot = round(float(df['close'].iloc[i]), 2)
            entry_time = df.index[i]
    
    if not trades:
        return None
    
    trades_df = pd.DataFrame(trades)
    trades_df['Exit Time'] = pd.to_datetime(trades_df['Exit Time'])
    trades_df['Month'] = trades_df['Exit Time'].dt.to_period('M')
    
    # Monthly stats
    monthly = trades_df.groupby('Month')['Net P&L'].sum().reset_index()
    monthly['ROI %'] = round((monthly['Net P&L'] / CAPITAL) * 100, 2)
    
    # Equity curve and drawdown
    equity = trades_df['Net P&L'].cumsum()
    peak = equity.cummax()
    drawdown = equity - peak
    max_dd = drawdown.min()
    max_dd_pct = round((max_dd / CAPITAL) * 100, 2)
    
    # Losing streak
    is_loss = (trades_df['Net P&L'] < 0).astype(int)
    streaks = is_loss * (is_loss.groupby((is_loss != is_loss.shift()).cumsum()).cumcount() + 1)
    max_losing_streak = int(streaks.max())
    
    # Profitable months
    profitable_months = len(monthly[monthly['Net P&L'] > 0])
    total_months = len(monthly)
    
    total_pnl = round(trades_df['Net P&L'].sum(), 2)
    avg_monthly_roi = round(monthly['ROI %'].mean(), 2)
    win_rate = round(len(trades_df[trades_df['Net P&L'] > 0]) / len(trades_df) * 100, 1)
    
    return {
        "Strategy": strategy_name,
        "Total Trades": len(trades_df),
        "Win Rate %": win_rate,
        "Annual P&L": total_pnl,
        "Annual ROI %": round((total_pnl / CAPITAL) * 100, 1),
        "Avg Monthly ROI %": avg_monthly_roi,
        "Profitable Months": f"{profitable_months}/{total_months}",
        "Max Drawdown $": round(max_dd, 2),
        "Max Drawdown %": max_dd_pct,
        "Max Losing Streak": max_losing_streak,
        "Monthly_Data": monthly
    }

# ========== FETCH DATA ==========
df = fetch_data()
if df.empty:
    print("No data!")
    exit()

# ========== PREPARE INDICATORS ==========
print("Calculating indicators...")

# Fast Supertrend (10, 1.5)
df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
fast_dir = "SUPERTd_10_1.5"

# Slow Supertrend (20, 3.0)
df = logic.calculate_supertrend(df, period=20, multiplier=3.0)
slow_dir = "SUPERTd_20_3.0"

# 50 EMA
df['ema_50'] = calc_ema(df['close'], 50)

# ADX
df['adx'] = calc_adx(df, 14)

# ========== STRATEGY 1: BASELINE (Plain ST 10, 1.5) ==========
def signal_baseline(df, i):
    prev = df[fast_dir].iloc[i-1]
    curr = df[fast_dir].iloc[i]
    if prev == -1 and curr == 1: return "BUY CE"
    if prev == 1 and curr == -1: return "BUY PE"
    return None

# ========== STRATEGY 2: DUAL SUPERTREND ==========
def signal_dual_st(df, i):
    fast_prev = df[fast_dir].iloc[i-1]
    fast_curr = df[fast_dir].iloc[i]
    slow_curr = df[slow_dir].iloc[i]
    
    # Fast ST flips AND slow ST agrees with direction
    if fast_prev == -1 and fast_curr == 1 and slow_curr == 1: return "BUY CE"
    if fast_prev == 1 and fast_curr == -1 and slow_curr == -1: return "BUY PE"
    return None

# ========== STRATEGY 3: EMA TREND FILTER ==========
def signal_ema_filter(df, i):
    fast_prev = df[fast_dir].iloc[i-1]
    fast_curr = df[fast_dir].iloc[i]
    price = df['close'].iloc[i]
    ema = df['ema_50'].iloc[i]
    
    # Only BUY CE when price above EMA (bullish environment)
    if fast_prev == -1 and fast_curr == 1 and price > ema: return "BUY CE"
    # Only BUY PE when price below EMA (bearish environment)
    if fast_prev == 1 and fast_curr == -1 and price < ema: return "BUY PE"
    return None

# ========== STRATEGY 4: ADX FILTER ==========
def signal_adx_filter(df, i):
    fast_prev = df[fast_dir].iloc[i-1]
    fast_curr = df[fast_dir].iloc[i]
    adx = df['adx'].iloc[i]
    
    # Only trade when ADX > 25 (trending market)
    if adx < 25: return None
    
    if fast_prev == -1 and fast_curr == 1: return "BUY CE"
    if fast_prev == 1 and fast_curr == -1: return "BUY PE"
    return None

# ========== STRATEGY 5: COMBINED FORTRESS ==========
def signal_fortress(df, i):
    fast_prev = df[fast_dir].iloc[i-1]
    fast_curr = df[fast_dir].iloc[i]
    slow_curr = df[slow_dir].iloc[i]
    price = df['close'].iloc[i]
    ema = df['ema_50'].iloc[i]
    adx = df['adx'].iloc[i]
    
    # ALL conditions must align
    if adx < 20: return None  # No ranging markets
    
    if fast_prev == -1 and fast_curr == 1 and slow_curr == 1 and price > ema: return "BUY CE"
    if fast_prev == 1 and fast_curr == -1 and slow_curr == -1 and price < ema: return "BUY PE"
    return None

# ========== RUN ALL STRATEGIES ==========
strategies = [
    ("1. BASELINE (ST 10,1.5)", signal_baseline),
    ("2. DUAL ST (10,1.5 + 20,3.0)", signal_dual_st),
    ("3. EMA 50 FILTER", signal_ema_filter),
    ("4. ADX > 25 FILTER", signal_adx_filter),
    ("5. FORTRESS (All Combined)", signal_fortress),
]

all_results = []
for name, func in strategies:
    print(f"Testing {name}...")
    result = run_strategy(df, name, func)
    if result:
        all_results.append(result)

# ========== PRINT COMPARISON ==========
print("\n" + "=" * 100)
print("DEEP STRATEGY RESEARCH: 12-MONTH BTC COMPARISON (ATM, 3-Day Expiry)")
print("=" * 100)

summary = pd.DataFrame([{k: v for k, v in r.items() if k != "Monthly_Data"} for r in all_results])
print(summary.to_string(index=False))

# Monthly comparison
print("\n" + "=" * 100)
print("MONTHLY ROI % BREAKDOWN (Side by Side)")
print("=" * 100)

monthly_pivot = {}
for r in all_results:
    md = r["Monthly_Data"]
    for _, row in md.iterrows():
        month = str(row['Month'])
        if month not in monthly_pivot: monthly_pivot[month] = {}
        monthly_pivot[month][r["Strategy"]] = f"{row['ROI %']}%"

pivot_df = pd.DataFrame.from_dict(monthly_pivot, orient='index')
pivot_df.index.name = "Month"
pivot_df = pivot_df.sort_index()
print(pivot_df.to_string())

# SUPREME CLOUD SYNC: 2026-04-30
