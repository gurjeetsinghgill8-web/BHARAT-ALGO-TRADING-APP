import yfinance as yf
import pandas as pd
import numpy as np
import logic
import datetime

def backtest_btc_rolling(target_pct):
    symbol = "BTC-USD"
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=180) # 6 Months
    
    df = yf.download(symbol, start=start_date, end=end_date, interval="1h", progress=False)
    if df.empty: return 0
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]

    df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
    dir_col = "SUPERTd_10_1.5"
    
    total_pnl = 0
    in_pos = False
    direction = 0
    entry_spot = 0
    
    for i in range(2, len(df)):
        last_dir = df[dir_col].iloc[i-1]
        prev_dir = df[dir_col].iloc[i-2]
        spot = df['close'].iloc[i]
        
        if (prev_dir == -1 and last_dir == 1) or (prev_dir == 1 and last_dir == -1):
            if in_pos:
                total_pnl += (spot - entry_spot if direction == 1 else entry_spot - spot) * 0.5
            direction = 1 if last_dir == 1 else -1
            entry_spot = spot
            in_pos = True
            continue
            
        if in_pos:
            move = (spot - entry_spot) if direction == 1 else (entry_spot - spot)
            opt_pnl_pct = (move * 0.5 / 120) * 100 # Assuming 120 entry
            
            if opt_pnl_pct >= target_pct:
                total_pnl += (target_pct / 100 * 120) # Book Target Pts
                entry_spot = spot # Roll
                
    return total_pnl

if __name__ == "__main__":
    print(">>> BITCOIN ROLLING TOURNAMENT (6 Months) <<<")
    print("-" * 50)
    
    std = backtest_btc_rolling(999999) # No rolling
    r30 = backtest_btc_rolling(30)
    r50 = backtest_btc_rolling(50)
    r100 = backtest_btc_rolling(100)
    
    print(f"Normal Buy & Hold : {std:.2f} pts")
    print(f"Rolling @ 30%     : {r30:.2f} pts")
    print(f"Rolling @ 50%     : {r50:.2f} pts")
    print(f"Rolling @ 100%    : {r100:.2f} pts")
    
    best = max(std, r30, r50, r100)
    if best == r30: print("\nWINNER: 30% ROLLING! Fast profit booking is best for BTC.")
    elif best == r50: print("\nWINNER: 50% ROLLING! Balanced approach is best for BTC.")
    elif best == r100: print("\nWINNER: 100% ROLLING! Letting it double is best for BTC.")
    else: print("\nWINNER: Normal Buy & Hold! BTC trends are too strong to cut short.")
