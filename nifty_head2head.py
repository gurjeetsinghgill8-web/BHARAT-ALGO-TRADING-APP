import yfinance as yf
import pandas as pd
import numpy as np
import logic
import datetime

def get_monthly_pnl(period, multiplier, timeframe="1h", lot_size=65):
    symbol = "^NSEI"
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=720) # ~2 years
    
    df = yf.download(symbol, start=start_date, end=end_date, interval=timeframe, progress=False)
    if df.empty: return pd.Series()
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]

    df = logic.calculate_supertrend(df, period=period, multiplier=multiplier)
    dir_col = f"SUPERTd_{period}_{multiplier}"
    
    trades = []
    in_pos = False
    entry = 0
    direction = 0
    entry_time = None
    
    for i in range(2, len(df)):
        last_dir = df[dir_col].iloc[i-1]
        prev_dir = df[dir_col].iloc[i-2]
        price = df['close'].iloc[i]
        
        if (prev_dir == -1 and last_dir == 1) or (prev_dir == 1 and last_dir == -1):
            if in_pos:
                pnl_pts = ((price - entry) if direction == 1 else (entry - price)) * 0.5
                trades.append({"month": entry_time.strftime('%Y-%m'), "pnl": pnl_pts * lot_size})
            entry = price
            direction = 1 if last_dir == 1 else -1
            entry_time = df.index[i]
            in_pos = True
            
    if not trades: return pd.Series()
    df_trades = pd.DataFrame(trades)
    return df_trades.groupby('month')['pnl'].sum()

def run_comparison():
    print(">>> NIFTY 2-YEAR HEAD-TO-HEAD: SURGICAL (10/2) VS AGGRESSIVE (10/1) <<<")
    print("Proxy Timeframe: 1h (Due to 2-year data limits) | Capital: Rs. 70,000")
    print("-" * 70)
    
    surgical = get_monthly_pnl(10, 2)
    aggressive = get_monthly_pnl(10, 1)
    
    comp = pd.DataFrame({
        "Surgical_10_2": surgical,
        "Aggressive_10_1": aggressive
    }).fillna(0)
    
    comp['Surgical_ROI_%'] = (comp['Surgical_10_2'] / 70000) * 100
    comp['Aggressive_ROI_%'] = (comp['Aggressive_10_1'] / 70000) * 100
    
    print(comp[['Surgical_ROI_%', 'Aggressive_ROI_%']].to_string())
    
    print("-" * 70)
    print(f"Total Surgical ROI   : {comp['Surgical_ROI_%'].sum():.2f}%")
    print(f"Total Aggressive ROI : {comp['Aggressive_ROI_%'].sum():.2f}%")
    print(f"Surgical Best Month  : {comp['Surgical_ROI_%'].max():.2f}%")
    print(f"Aggressive Best Month: {comp['Aggressive_ROI_%'].max():.2f}%")
    print(f"Surgical Worst Month : {comp['Surgical_ROI_%'].min():.2f}%")
    print(f"Aggressive Worst Month: {comp['Aggressive_ROI_%'].min():.2f}%")

if __name__ == "__main__":
    run_comparison()

# SUPREME CLOUD SYNC: 2026-04-30
