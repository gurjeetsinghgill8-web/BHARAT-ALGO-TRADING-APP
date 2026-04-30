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

def run_adx_strategy(ticker, label):
    print(f"Downloading 12 months of 1H {label} data...")
    df = yf.download(ticker, period="365d", interval="1h", progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    if df.empty:
        print(f"No data for {label}")
        return None

    df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
    fast_dir = "SUPERTd_10_1.5"
    df['adx'] = calc_adx(df, 14)

    trades = []
    current_pos = None
    entry_spot = 0.0

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

    print(f"\n{'='*70}")
    print(f"  {label} - ADX FILTER (1H | 10,1.5 | ATM) - 12 MONTH REPORT")
    print(f"{'='*70}")
    print(f"{'Month':<12} {'Trades':>7} {'P&L ($)':>12} {'Monthly ROI':>13}")
    print("-" * 70)
    for _, row in monthly.iterrows():
        s = "[+]" if row['Net_PnL'] > 0 else "[-]"
        print(f"{s} {str(row['Month']):<10} {row['Trades']:>5}   ${row['Net_PnL']:>10,.2f}   {row['ROI %']:>10}%")
    print("-" * 70)
    print(f"  Annual P&L:          ${total_pnl:,.2f}")
    print(f"  Annual ROI:          {(total_pnl/CAPITAL)*100:.1f}%")
    print(f"  Avg Monthly ROI:     {monthly['ROI %'].mean():.2f}%")
    print(f"  Profitable Months:   {profitable_months}/{len(monthly)}")
    print(f"  Max Drawdown:        ${max_dd:,.2f} ({(max_dd/CAPITAL)*100:.1f}%)")
    print(f"  Win Rate:            {len(trades_df[trades_df['Net P&L']>0])/len(trades_df)*100:.1f}%")
    print(f"{'='*70}")

    return {
        "Asset": label,
        "Annual P&L": round(total_pnl, 2),
        "Annual ROI %": round((total_pnl/CAPITAL)*100, 1),
        "Avg Monthly ROI %": round(monthly['ROI %'].mean(), 2),
        "Profitable Months": f"{profitable_months}/{len(monthly)}",
        "Max Drawdown %": round((max_dd/CAPITAL)*100, 1),
        "Win Rate %": round(len(trades_df[trades_df['Net P&L']>0])/len(trades_df)*100, 1),
        "Total Trades": len(trades_df)
    }

btc = run_adx_strategy("BTC-USD", "BITCOIN (BTC)")
eth = run_adx_strategy("ETH-USD", "ETHEREUM (ETH)")

print("\n" + "=" * 70)
print("  BTC vs ETH - HEAD TO HEAD COMPARISON")
print("=" * 70)
comp = pd.DataFrame([btc, eth])
print(comp.to_string(index=False))

# SUPREME CLOUD SYNC: 2026-04-30
