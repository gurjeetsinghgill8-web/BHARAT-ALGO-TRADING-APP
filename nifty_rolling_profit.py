import yfinance as yf
import pandas as pd
import numpy as np
import logic
import datetime

def backtest_rolling(period, multiplier, timeframe="1h", target_premium=120, tp_pct=50):
    symbol = "^NSEI"
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365) # 1 Year
    
    df = yf.download(symbol, start=start_date, end=end_date, interval=timeframe, progress=False)
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]

    df = logic.calculate_supertrend(df, period=period, multiplier=multiplier)
    dir_col = f"SUPERTd_{period}_{multiplier}"
    
    # 1. Standard "Buy & Hold until Flip"
    std_pnl = 0
    std_trades = []
    
    # 2. Rolling "50% Profit Booking"
    roll_pnl = 0
    roll_trades = []
    
    # Common vars
    in_pos = False
    direction = 0
    entry_spot = 0
    std_entry_spot = 0
    roll_count = 0
    
    for i in range(2, len(df)):
        last_dir = df[dir_col].iloc[i-1]
        prev_dir = df[dir_col].iloc[i-2]
        spot = df['close'].iloc[i]
        
        # Supertrend Flip
        if (prev_dir == -1 and last_dir == 1) or (prev_dir == 1 and last_dir == -1):
            if in_pos:
                std_pnl += (spot - std_entry_spot if direction == 1 else std_entry_spot - spot) * 0.5
                roll_pnl += (spot - entry_spot if direction == 1 else entry_spot - spot) * 0.5
            
            direction = 1 if last_dir == 1 else -1
            std_entry_spot = spot
            entry_spot = spot
            in_pos = True
            continue
            
        if in_pos:
            spot_move = (spot - entry_spot) if direction == 1 else (entry_spot - spot)
            opt_gain = spot_move * 0.5
            if opt_gain >= (target_premium * (tp_pct/100)):
                roll_pnl += opt_gain
                entry_spot = spot
                roll_count += 1
                
    return {"Standard_PNL": std_pnl, "Rolling_PNL": roll_pnl, "Roll_Count": roll_count}

def run_game_changer():
    print(">>> NIFTY GAME CHANGER: ROLLING PROFIT (50%) VS BUY & HOLD <<<")
    res = backtest_rolling(10, 1, "1h")
    if res:
        print(f"Standard Strategy PNL : {res['Standard_PNL']:.2f}")
        print(f"Rolling Strategy PNL  : {res['Rolling_PNL']:.2f}")
        print(f"Total Rollovers       : {res['Roll_Count']}")
        
        diff = res['Rolling_PNL'] - res['Standard_PNL']
        print("-" * 70)
        print(f"DIFFERENCE: {diff:+.2f} points")
        if diff > 0:
            print("Verdict: GAME CHANGER IS BETTER! Profit booking locks in gains during spikes.")
        else:
            print("Verdict: Buy & Hold is better. Rolling might be cutting winners too short.")

if __name__ == "__main__":
    run_game_changer()

# SUPREME CLOUD SYNC: 2026-04-30
