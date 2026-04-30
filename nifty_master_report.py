import yfinance as yf
import pandas as pd
import numpy as np
import logic
import datetime

def backtest(period, multiplier, timeframe, days=90):
    symbol = "^NSEI"
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=days)
    
    # yfinance limits
    if timeframe in ["15m", "30m"] and days > 59:
        days = 59
        start_date = end_date - datetime.timedelta(days=days)

    df = yf.download(symbol, start=start_date, end=end_date, interval=timeframe, progress=False)
    if df.empty: return None
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]

    df = logic.calculate_supertrend(df, period=period, multiplier=multiplier)
    dir_col = f"SUPERTd_{period}_{multiplier}"
    
    trades = []
    in_pos = False
    entry = 0
    direction = 0
    
    for i in range(2, len(df)):
        last_dir = df[dir_col].iloc[i-1]
        prev_dir = df[dir_col].iloc[i-2]
        price = df['close'].iloc[i]
        
        if (prev_dir == -1 and last_dir == 1) or (prev_dir == 1 and last_dir == -1):
            if in_pos:
                pnl = (price - entry) if direction == 1 else (entry - price)
                trades.append(pnl)
            entry = price
            direction = 1 if last_dir == 1 else -1
            in_pos = True
            
    if not trades: return {"pnl": 0, "win": 0, "cnt": 0}
    return {"pnl": round(sum(trades), 2), "win": round(len([t for t in trades if t > 0])/len(trades)*100, 1), "cnt": len(trades)}

def master_report():
    print("Generating Master Nifty Report...")
    tfs = ["15m", "30m", "1h", "1d"]
    mults = [1, 1.5, 2]
    
    results = []
    for tf in tfs:
        for m in mults:
            res = backtest(10, m, tf, 90)
            if res:
                results.append({"Timeframe": tf, "ST_Param": f"10/{m}", "PNL_Pts": res['pnl'], "WinRate_%": res['win'], "Trades": res['cnt']})

    df_rank = pd.DataFrame(results).sort_values(by="PNL_Pts", ascending=False)
    
    # Monthly ROI for Winner (Assuming 1h for 1 year data)
    symbol = "^NSEI"
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365)
    df_1y = yf.download(symbol, start=start_date, end=end_date, interval="1h", progress=False)
    if isinstance(df_1y.columns, pd.MultiIndex): df_1y.columns = df_1y.columns.get_level_values(0)
    df_1y.columns = [str(c).lower() for c in df_1y.columns]
    
    # Best Settings: 10/1.5 (Balanced)
    df_1y = logic.calculate_supertrend(df_1y, 10, 1)
    df_1y['month'] = df_1y.index.strftime('%Y-%m')
    
    lot_size = 65
    capital = 70000
    
    y_trades = []
    in_pos = False
    entry = 0
    direction = 0
    entry_time = None
    
    for i in range(2, len(df_1y)):
        last_dir = df_1y["SUPERTd_10_1"].iloc[i-1]
        prev_dir = df_1y["SUPERTd_10_1"].iloc[i-2]
        price = df_1y['close'].iloc[i]
        
        if (prev_dir == -1 and last_dir == 1) or (prev_dir == 1 and last_dir == -1):
            if in_pos:
                pnl_pts = ((price - entry) if direction == 1 else (entry - price)) * 0.5
                y_trades.append({"month": entry_time.strftime('%Y-%m'), "cash_pnl": pnl_pts * lot_size})
            entry = price
            direction = 1 if last_dir == 1 else -1
            entry_time = df_1y.index[i]
            in_pos = True
            
    df_y = pd.DataFrame(y_trades)
    monthly = df_y.groupby('month')['cash_pnl'].sum().reset_index()
    monthly['ROI_%'] = (monthly['cash_pnl'] / capital) * 100
    
    print("\n--- 3-MONTH TOURNAMENT TABLE ---")
    print(df_rank.to_string(index=False))
    print("\n--- 1-YEAR MONTHLY ROI TABLE (ST 10/1) ---")
    print(monthly.to_string(index=False))

if __name__ == "__main__":
    master_report()

# SUPREME CLOUD SYNC: 2026-04-30
