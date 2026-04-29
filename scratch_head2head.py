"""
HEAD-TO-HEAD: ADX Filter Strategy vs Stable Wealth Strategy (EMA 200 + ST 10,2)
================================================================================
Strategy A (OURS):  ADX > 25 Filter + Supertrend (10, 1.5) on 1H
Strategy B (THEIRS): Price vs 200 EMA Filter + Supertrend (10, 2.0) on 1H
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

def calc_adx(df, period=14):
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
    return adx

def run_strategy(df, name, signal_func):
    trades = []
    current_pos = None
    entry_spot = 0.0

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
                trades.append({"Exit Time": df.index[i], "Net P&L": net_pnl})
            current_pos = signal
            entry_spot = round(float(df['close'].iloc[i]), 2)

    if not trades: return None
    trades_df = pd.DataFrame(trades)
    trades_df['Exit Time'] = pd.to_datetime(trades_df['Exit Time'])
    trades_df['Month'] = trades_df['Exit Time'].dt.to_period('M')

    monthly = trades_df.groupby('Month').agg(
        Trades=('Net P&L', 'count'),
        Net_PnL=('Net P&L', 'sum')
    ).reset_index()
    monthly['ROI %'] = round((monthly['Net_PnL'] / CAPITAL) * 100, 2)

    equity = trades_df['Net P&L'].cumsum()
    max_dd = (equity - equity.cummax()).min()
    total_pnl = trades_df['Net P&L'].sum()
    profitable_months = len(monthly[monthly['Net_PnL'] > 0])
    
    # Max losing streak
    is_loss = (trades_df['Net P&L'] < 0).astype(int)
    streaks = is_loss * (is_loss.groupby((is_loss != is_loss.shift()).cumsum()).cumcount() + 1)
    max_losing_streak = int(streaks.max())

    return {
        "Strategy": name,
        "Total Trades": len(trades_df),
        "Win Rate %": round(len(trades_df[trades_df['Net P&L']>0])/len(trades_df)*100, 1),
        "Annual P&L": round(total_pnl, 2),
        "Annual ROI %": round((total_pnl/CAPITAL)*100, 1),
        "Avg Monthly ROI %": round(monthly['ROI %'].mean(), 2),
        "Profitable Months": f"{profitable_months}/{len(monthly)}",
        "Max Drawdown %": round((max_dd/CAPITAL)*100, 1),
        "Max Losing Streak": max_losing_streak,
        "Monthly_Data": monthly
    }

# ========== FETCH DATA ==========
print("Downloading 12 months of 1H BTC data...")
df = yf.download("BTC-USD", period="365d", interval="1h", progress=False)
if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
df.columns = [str(c).lower() for c in df.columns]

# ========== CALCULATE ALL INDICATORS ==========
print("Calculating indicators...")

# For ADX Strategy: ST (10, 1.5)
df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
adx_dir = "SUPERTd_10_1.5"

# For Stable Wealth: ST (10, 2.0)
df = logic.calculate_supertrend(df, period=10, multiplier=2.0)
sw_dir = "SUPERTd_10_2.0"

# ADX
df['adx'] = calc_adx(df, 14)

# 200 EMA
df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

# ========== STRATEGY A: OUR ADX FILTER ==========
def signal_adx(df, i):
    prev = df[adx_dir].iloc[i-1]
    curr = df[adx_dir].iloc[i]
    adx = df['adx'].iloc[i]
    if adx < 25: return None
    if prev == -1 and curr == 1: return "BUY CE"
    if prev == 1 and curr == -1: return "BUY PE"
    return None

# ========== STRATEGY B: STABLE WEALTH (EMA 200 + ST 10,2) ==========
def signal_stable_wealth(df, i):
    prev = df[sw_dir].iloc[i-1]
    curr = df[sw_dir].iloc[i]
    price = float(df['close'].iloc[i])
    ema200 = float(df['ema_200'].iloc[i])
    
    # CE only when Price > EMA200 AND ST flips green
    if prev == -1 and curr == 1 and price > ema200: return "BUY CE"
    # PE only when Price < EMA200 AND ST flips red
    if prev == 1 and curr == -1 and price < ema200: return "BUY PE"
    return None

# ========== RUN BOTH ==========
print("Testing Strategy A: ADX Filter (10,1.5)...")
res_a = run_strategy(df, "A: ADX Filter (10,1.5)", signal_adx)

print("Testing Strategy B: Stable Wealth (EMA200 + 10,2)...")
res_b = run_strategy(df, "B: Stable Wealth (EMA200 + 10,2)", signal_stable_wealth)

# ========== PRINT COMPARISON ==========
print("\n" + "=" * 80)
print("  HEAD-TO-HEAD: ADX Filter vs Stable Wealth Strategy")
print("=" * 80)

metrics = ["Strategy", "Total Trades", "Win Rate %", "Annual P&L", "Annual ROI %", 
           "Avg Monthly ROI %", "Profitable Months", "Max Drawdown %", "Max Losing Streak"]
for m in metrics:
    a_val = res_a[m] if res_a else "N/A"
    b_val = res_b[m] if res_b else "N/A"
    print(f"  {m:<25} {str(a_val):>20}   {str(b_val):>20}")

# ========== MONTHLY SIDE-BY-SIDE ==========
print("\n" + "=" * 80)
print("  MONTHLY ROI % COMPARISON")
print("=" * 80)
print(f"  {'Month':<12} {'ADX Filter':>15} {'Stable Wealth':>15} {'Winner':>12}")
print("-" * 80)

md_a = {str(r['Month']): r for _, r in res_a['Monthly_Data'].iterrows()} if res_a else {}
md_b = {str(r['Month']): r for _, r in res_b['Monthly_Data'].iterrows()} if res_b else {}
all_months = sorted(set(list(md_a.keys()) + list(md_b.keys())))

for m in all_months:
    roi_a = md_a[m]['ROI %'] if m in md_a else 0
    roi_b = md_b[m]['ROI %'] if m in md_b else 0
    winner = "ADX" if roi_a > roi_b else "STABLE" if roi_b > roi_a else "TIE"
    print(f"  {m:<12} {roi_a:>14}% {roi_b:>14}% {winner:>12}")
