import yfinance as yf
import pandas as pd
import numpy as np
import logic
import datetime

def check_15m_final():
    symbol = "^NSEI"
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=59)
    
    df = yf.download(symbol, start=start_date, end=end_date, interval="15m", progress=False)
    if df.empty: return
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]

    # Calculate both
    df_s = logic.calculate_supertrend(df.copy(), 10, 2)
    df_a = logic.calculate_supertrend(df.copy(), 10, 1)
    
    def get_stats(data, col):
        trades = []
        in_pos = False
        entry = 0
        direction = 0
        for i in range(2, len(data)):
            last_dir = data[col].iloc[i-1]
            prev_dir = data[col].iloc[i-2]
            price = data['close'].iloc[i]
            if (prev_dir == -1 and last_dir == 1) or (prev_dir == 1 and last_dir == -1):
                if in_pos: trades.append((price - entry) if direction == 1 else (entry - price))
                entry = price
                direction = 1 if last_dir == 1 else -1
                in_pos = True
        if not trades: return 0, 0, 0
        return sum(trades), (len([t for t in trades if t > 0])/len(trades)*100), len(trades)

    p_s, w_s, c_s = get_stats(df_s, "SUPERTd_10_2")
    p_a, w_a, c_a = get_stats(df_a, "SUPERTd_10_1")
    
    print(f"Final 60-Day 15m Check:")
    print(f"SURGICAL (10/2): PNL {p_s:.2f} pts | WinRate {w_s:.1f}% | Trades {c_s}")
    print(f"AGGRESSIVE (10/1): PNL {p_a:.2f} pts | WinRate {w_a:.1f}% | Trades {c_a}")

if __name__ == "__main__":
    check_15m_final()
