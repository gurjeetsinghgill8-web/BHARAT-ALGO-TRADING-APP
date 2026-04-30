import yfinance as yf
import pandas as pd
import numpy as np
import logic
import datetime

def run_nifty_backtest(period, multiplier, timeframe):
    symbol = "^NSEI"
    end_date = datetime.datetime.now()
    
    # yfinance limits: 15m/30m data only available for last 60 days
    days = 59 if timeframe in ["15m", "30m"] else 90
    start_date = end_date - datetime.timedelta(days=days)
    
    df = yf.download(symbol, start=start_date, end=end_date, interval=timeframe, progress=False)
    if df.empty:
        return None
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]

    df = logic.calculate_supertrend(df, period=period, multiplier=multiplier)
    
    trades = []
    in_position = False
    entry_price = 0
    direction = 0
    
    dir_col = f"SUPERTd_{period}_{multiplier}"
    
    for i in range(2, len(df)):
        last_dir = df[dir_col].iloc[i-1]
        prev_dir = df[dir_col].iloc[i-2]
        price = df['close'].iloc[i]
        
        if prev_dir == -1 and last_dir == 1:
            if in_position:
                pnl = (price - entry_price) if direction == 1 else (entry_price - price)
                trades.append(pnl)
            entry_price = price
            direction = 1
            in_position = True
        elif prev_dir == 1 and last_dir == -1:
            if in_position:
                pnl = (price - entry_price) if direction == 1 else (entry_price - price)
                trades.append(pnl)
            entry_price = price
            direction = -1
            in_position = True
            
    if not trades:
        return {"total_pnl": 0, "win_rate": 0, "count": 0}
        
    total_pnl = sum(trades)
    win_rate = (len([t for t in trades if t > 0]) / len(trades)) * 100
    
    return {
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 2),
        "count": len(trades)
    }

def start_tournament():
    print(">>> NIFTY TOURNAMENT STARTING...")
    print("Params: Supertrend (10,1), (10,1.5), (10,2) | Timeframes: 15m, 30m, 1h, 1d")
    print("-" * 60)
    
    results = []
    multipliers = [1, 1.5, 2]
    timeframes = ["15m", "30m", "1h", "1d"]
    
    for tf in timeframes:
        for m in multipliers:
            res = run_nifty_backtest(10, m, tf)
            if res:
                results.append({
                    "TF": tf,
                    "ST": f"10/{m}",
                    "PNL_Pts": res['total_pnl'],
                    "WinRate": res['win_rate'],
                    "Trades": res['count']
                })
                print(f"DONE: {tf} | 10/{m} -> PNL: {res['total_pnl']} pts")
                
    results_df = pd.DataFrame(results).sort_values(by="PNL_Pts", ascending=False)
    print("\n" + "="*60)
    print("RANKING: FINAL NIFTY TOURNAMENT RANKING")
    print("="*60)
    print(results_df.to_string(index=False))
    print("="*60)
    
    if not results_df.empty:
        best = results_df.iloc[0]
        print(f"\nWINNER: {best['TF']} with ST {best['ST']} (PNL: {best['PNL_Pts']} pts)")

if __name__ == "__main__":
    start_tournament()

# SUPREME CLOUD SYNC: 2026-04-30
