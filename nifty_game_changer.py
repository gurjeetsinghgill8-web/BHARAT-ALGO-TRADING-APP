import yfinance as yf
import pandas as pd
import numpy as np
import logic
import datetime

def backtest_game_changer(period, multiplier, timeframe="1h"):
    symbol = "^NSEI"
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365)
    
    df = yf.download(symbol, start=start_date, end=end_date, interval=timeframe, progress=False)
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]

    df = logic.calculate_supertrend(df, period=period, multiplier=multiplier)
    dir_col = f"SUPERTd_{period}_{multiplier}"
    
    target_prem = 120
    std_pnl = 0
    roll_pnl = 0
    
    in_pos = False
    direction = 0
    std_entry = 0
    roll_entry = 0
    
    for i in range(2, len(df)):
        last_dir = df[dir_col].iloc[i-1]
        prev_dir = df[dir_col].iloc[i-2]
        spot = df['close'].iloc[i]
        
        if (prev_dir == -1 and last_dir == 1) or (prev_dir == 1 and last_dir == -1):
            if in_pos:
                # Close Both
                std_pnl += (spot - std_entry if direction == 1 else std_entry - spot) * 0.5
                roll_pnl += (spot - roll_entry if direction == 1 else roll_entry - spot) * 0.5
            
            direction = 1 if last_dir == 1 else -1
            std_entry = spot
            roll_entry = spot
            in_pos = True
            continue
            
        if in_pos:
            # Check Rolling Condition (50% Profit)
            move = (spot - roll_entry) if direction == 1 else (roll_entry - spot)
            opt_pnl = move * 0.5
            
            # 1. Take Profit at 50% (+60 pts)
            if opt_pnl >= 60:
                roll_pnl += 60
                roll_entry = spot # Roll to current spot
                # print("Hit +50%! Rolling...")
                
            # 2. Safety SL at -25% (-30 pts) from last roll
            elif opt_pnl <= -30:
                roll_pnl += -30
                # After SL, we stay OUT of rolling until next ST flip to be safe? 
                # No, user says "sem direction mein buy kar lena". So we re-enter at current spot.
                roll_entry = spot
                # print("Hit -25% SL! Re-entering...")

    return std_pnl, roll_pnl

if __name__ == "__main__":
    print(">>> THE WORLD'S BEST STRATEGY: ROLLING PROFIT + SAFETY SL <<<")
    s, r = backtest_game_changer(10, 1, "1h")
    print(f"Standard PNL: {s:.2f} pts")
    print(f"Rolling PNL : {r:.2f} pts")
    print(f"IMPROVEMENT : {((r-s)/s)*100 if s!=0 else 0:.2f}%")

# SUPREME CLOUD SYNC: 2026-04-30
