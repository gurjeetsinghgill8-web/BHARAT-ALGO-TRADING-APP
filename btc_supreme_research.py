import yfinance as yf
import pandas as pd
import numpy as np
import logic
import datetime

def run_btc_backtest(st_period, st_mult, timeframe, strike_type, expiry_days):
    """
    Simulates BTC Options trading.
    strike_type: 'ATM', 'OTM3', 'ITM3'
    expiry_days: 3, 7, 30, 60
    """
    # Fetch 60 days of 5m data (max allowed by yfinance)
    df = yf.download('BTC-USD', period='60d', interval=timeframe, progress=False)
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    
    df = logic.calculate_supertrend(df, period=st_period, multiplier=st_mult)
    dir_col = f"SUPERTd_{st_period}_{st_mult}"
    
    trades = []
    active_pos = None
    
    # Premium Simulation (Approximate)
    # ATM usually costs ~2% of spot for weekly
    # OTM3 costs ~0.5%
    # ITM3 costs ~5%
    cost_map = {'ATM': 0.02, 'OTM3': 0.005, 'ITM3': 0.05}
    cost_mult = cost_map.get(strike_type, 0.02)
    
    for i in range(1, len(df)):
        signal = df[dir_col].iloc[i]
        prev_signal = df[dir_col].iloc[i-1]
        price = df['close'].iloc[i]
        timestamp = df.index[i]
        
        # Crossover logic
        if prev_signal == -1 and signal == 1: # BUY
            if active_pos: trades[-1]['exit_price'] = price; trades[-1]['exit_time'] = timestamp
            active_pos = {'type': 'BUY', 'entry_price': price, 'entry_time': timestamp}
            trades.append(active_pos)
        elif prev_signal == 1 and signal == -1: # SELL
            if active_pos: trades[-1]['exit_price'] = price; trades[-1]['exit_time'] = timestamp
            active_pos = {'type': 'SELL', 'entry_price': price, 'entry_time': timestamp}
            trades.append(active_pos)
            
    # Calculate PnL with Option Leverage (Approx 10x for BTC options)
    # PnL = (Exit - Entry) / Entry * 10 (Leverage)
    results = []
    for t in trades:
        if 'exit_price' in t:
            pnl_pct = (t['exit_price'] - t['entry_price']) / t['entry_price']
            if t['type'] == 'SELL': pnl_pct = -pnl_pct
            
            # Options PnL (Simplified: 10x leverage minus theta decay)
            # Short expiries (3d) have higher theta decay
            theta_decay = (0.005 if expiry_days <= 7 else 0.001)
            opt_pnl = (pnl_pct * 10) - theta_decay
            results.append(opt_pnl)
            
    total_roi = sum(results) * 100
    return total_roi

# Running the Tournament
timeframe = "5m"
combinations = [
    (10, 1.0), (10, 1.5), (10, 2.0)
]
strikes = ['ATM', 'OTM3', 'ITM3']
expiries = [3, 7, 30]

data = []
print("Starting BTC Supreme Research...")

for period, mult in combinations:
    for s in strikes:
        for exp in expiries:
            roi = run_btc_backtest(period, mult, timeframe, s, exp)
            data.append({
                "Strategy": f"ST {period}/{mult}",
                "Strike": s,
                "Expiry": f"{exp}d",
                "60d ROI (%)": round(roi, 2)
            })

report_df = pd.DataFrame(data)
report_df = report_df.sort_values(by="60d ROI (%)", ascending=False)
print(report_df.to_string(index=False))

# Save report
report_df.to_csv("btc_supreme_report.csv", index=False)
