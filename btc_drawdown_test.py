import yfinance as yf
import pandas as pd
import numpy as np
import logic

def calculate_drawdown(pnl_list):
    if not pnl_list: return 0
    cum_pnl = np.cumsum(pnl_list)
    peak = np.maximum.accumulate(cum_pnl)
    drawdown = (peak - cum_pnl).max()
    return round(drawdown * 100, 2)

def backtest_engine_v2(df, st_period, st_mult, delta):
    df = logic.calculate_supertrend(df, period=st_period, multiplier=st_mult)
    dir_col = next((c for c in df.columns if f"SUPERTd_{st_period}_{st_mult}" in c), None)
    
    pos = 0
    trade_results = []
    
    for i in range(1, len(df)):
        signal = df[dir_col].iloc[i]
        prev_sig = df[dir_col].iloc[i-1]
        price = df['close'].iloc[i]
        
        if prev_sig == -1 and signal == 1:
            if pos != 0: 
                move = (price - entry_price) / entry_price
                if pos == -1: move = -move
                trade_results.append((move * 20 * delta) - 0.002)
            pos = 1
            entry_price = price
        elif prev_sig == 1 and signal == -1:
            if pos != 0:
                move = (price - entry_price) / entry_price
                if pos == -1: move = -move
                trade_results.append((move * 20 * delta) - 0.002)
            pos = -1
            entry_price = price
            
    total_roi = sum(trade_results)
    max_dd = calculate_drawdown(trade_results)
    return total_roi, max_dd, len(trade_results)

df5m = yf.download('BTC-USD', period='60d', interval='5m', progress=False)
df15m = yf.download('BTC-USD', period='60d', interval='15m', progress=False)

for d in [df5m, df15m]:
    if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
    d.columns = [str(c).lower().strip() for c in d.columns]

results = []
for tf_name, df in [('5m', df5m), ('15m', df15m)]:
    roi, dd, count = backtest_engine_v2(df, 10, 1.5, 0.5) # ATM
    results.append({
        "Timeframe": tf_name,
        "Total ROI (60d)": f"{roi*100:.1f}%",
        "Max Drawdown": f"{dd}%",
        "Total Trades": count
    })

print("\n>>> BTC DRAWDOWN ANALYSIS: 5M vs 15M <<<")
print(pd.DataFrame(results).to_string(index=False))
