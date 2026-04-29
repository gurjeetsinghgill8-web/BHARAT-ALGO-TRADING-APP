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

print("Downloading 12 months of 1H BTC data...")
df = yf.download("BTC-USD", period="365d", interval="1h", progress=False)
if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
df.columns = [str(c).lower() for c in df.columns]

# Calculate indicators
df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
fast_dir = "SUPERTd_10_1.5"
df['adx'] = calc_adx(df, 14)

# Run ADX Filter strategy
trades = []
current_pos = None
entry_spot = 0.0
entry_time = None

for i in range(2, len(df)):
    fast_prev = df[fast_dir].iloc[i-1]
    fast_curr = df[fast_dir].iloc[i]
    adx = df['adx'].iloc[i]
    
    signal = None
    if adx >= 25:
        if fast_prev == -1 and fast_curr == 1: signal = "BUY CE"
        elif fast_prev == 1 and fast_curr == -1: signal = "BUY PE"
    
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
                "Net P&L": net_pnl
            })
        current_pos = signal
        entry_spot = round(float(df['close'].iloc[i]), 2)
        entry_time = df.index[i]

trades_df = pd.DataFrame(trades)
trades_df['Exit Time'] = pd.to_datetime(trades_df['Exit Time'])
trades_df['Month'] = trades_df['Exit Time'].dt.to_period('M')

monthly = trades_df.groupby('Month').agg(
    Trades=('Net P&L', 'count'),
    Wins=('Net P&L', lambda x: (x > 0).sum()),
    Losses=('Net P&L', lambda x: (x <= 0).sum()),
    Net_PnL=('Net P&L', 'sum')
).reset_index()

monthly['Win Rate %'] = round((monthly['Wins'] / monthly['Trades']) * 100, 1)
monthly['Monthly ROI %'] = round((monthly['Net_PnL'] / CAPITAL) * 100, 2)

# Equity for drawdown tracking
equity = trades_df['Net P&L'].cumsum()
peak = equity.cummax()
drawdown = equity - peak

print("\n" + "=" * 85)
print("  ADX > 25 FILTER STRATEGY — 12-MONTH DETAILED REPORT")
print("  Setup: 1 Hour | ST (10, 1.5) | ATM 3-Day Expiry | Capital: $5,000")
print("=" * 85)
print(f"{'Month':<12} {'Trades':>7} {'Wins':>6} {'Losses':>8} {'Win Rate':>10} {'P&L ($)':>12} {'Monthly ROI':>13}")
print("-" * 85)

for _, row in monthly.iterrows():
    pnl_str = f"${row['Net_PnL']:,.2f}"
    roi_str = f"{row['Monthly ROI %']}%"
    status = "[+]" if row['Net_PnL'] > 0 else "[-]"
    print(f"{status} {str(row['Month']):<10} {row['Trades']:>7} {row['Wins']:>6} {row['Losses']:>8} {row['Win Rate %']:>9}% {pnl_str:>12} {roi_str:>13}")

total_pnl = trades_df['Net P&L'].sum()
avg_monthly_roi = monthly['Monthly ROI %'].mean()
max_dd = drawdown.min()
profitable_months = len(monthly[monthly['Net_PnL'] > 0])
total_months = len(monthly)

print("-" * 85)
print(f"  TOTAL ANNUAL P&L:        ${total_pnl:,.2f}")
print(f"  TOTAL ANNUAL ROI:        {(total_pnl/CAPITAL)*100:.1f}%")
print(f"  AVG MONTHLY ROI:         {avg_monthly_roi:.2f}%")
print(f"  PROFITABLE MONTHS:       {profitable_months} / {total_months}")
print(f"  MAX DRAWDOWN:            ${max_dd:,.2f} ({(max_dd/CAPITAL)*100:.1f}%)")
print(f"  TOTAL TRADES:            {len(trades_df)}")
print(f"  OVERALL WIN RATE:        {len(trades_df[trades_df['Net P&L']>0])/len(trades_df)*100:.1f}%")
print("=" * 85)
