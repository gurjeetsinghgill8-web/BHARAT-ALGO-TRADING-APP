import pandas as pd
import numpy as np
import logic
import db
import os
from datetime import datetime
import pytz

def fetch_historical_data(timeframe, start_date, end_date):
    """
    Fetches REAL Nifty 50 data for a specific date range.
    Handles interval availability (15m is limited to last 60 days).
    """
    import yfinance as yf
    
    interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h"}
    yf_interval = interval_map.get(timeframe, "1h")
    
    # If the date is more than 60 days ago, yfinance might fail for 15m.
    # We will try the requested interval, and fallback to 1h if it's an old range.
    days_diff = (datetime.now() - datetime.strptime(start_date, "%Y-%m-%d")).days
    if days_diff > 58 and yf_interval in ["15m", "30m", "5m", "1m"]:
        print(f"[Backtester] Range is {days_diff} days. Switching to 1h interval due to API limits.")
        yf_interval = "1h"

    print(f"[Backtester] Downloading ^NSEI ({yf_interval}) from {start_date} to {end_date}...")
    
    try:
        df = yf.download("^NSEI", start=start_date, end=end_date, interval=yf_interval, progress=False)
        
        if df.empty:
            raise Exception("Yahoo Finance returned empty data.")
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df.columns = [c.lower() for c in df.columns]
        
        # Convert to IST
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC')
        df.index = df.index.tz_convert('Asia/Kolkata')
        
        # Filter for Indian Market Hours
        df = df.between_time('09:15', '15:30')
        
        return df
    except Exception as e:
        print(f"⚠️ Data Fetch Failed: {e}")
        return pd.DataFrame()

def run_backtest(period, multiplier, timeframe, start_date=None, end_date=None):
    """
    Runs backtest for a specific range and parameters.
    """
    # Default to April range if not provided
    if not start_date:
        start_date = "2026-04-01"
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
        
    df = fetch_historical_data(timeframe, start_date, end_date)
    if df.empty:
        return {"error": "Could not fetch real Nifty data."}
    
    # Calculate Supertrend
    db.set_param('st_period', period)
    db.set_param('st_multiplier', multiplier)
    df_st = logic.calculate_supertrend(df)
    
    dir_col = f"SUPERTd_{int(period)}_{float(multiplier)}"
    if dir_col not in df_st.columns:
        return {"error": "Supertrend Calculation Error."}
        
    trades = []
    current_pos = None
    entry_price = 0.0
    
    df_st['prev_dir'] = df_st[dir_col].shift(1)
    
    for idx, row in df_st.dropna(subset=[dir_col, 'prev_dir']).iterrows():
        prev_dir = row['prev_dir']
        last_dir = row[dir_col]
        
        signal = None
        if prev_dir == -1 and last_dir == 1:
            signal = "BUY CE"
        elif prev_dir == 1 and last_dir == -1:
            signal = "BUY PE"
            
        if signal and signal != current_pos:
            if current_pos:
                exit_price = round(float(row['close']), 2)
                raw_pnl = (exit_price - entry_price) if "CE" in current_pos else (entry_price - exit_price)
                trades.append({
                    "Time (IST)": idx.strftime("%Y-%m-%d %H:%M"),
                    "Action": f"SQUARE OFF {current_pos}",
                    "Nifty Spot": exit_price,
                    "PnL (Points)": round(raw_pnl, 2)
                })
            
            current_pos = signal
            entry_price = round(float(row['close']), 2)
            trades.append({
                "Time (IST)": idx.strftime("%Y-%m-%d %H:%M"),
                "Action": f"ENTRY {current_pos}",
                "Nifty Spot": entry_price,
                "PnL (Points)": 0.0
            })

    trades_df = pd.DataFrame(trades)
    
    if trades_df.empty:
         return {"Total Trades": 0, "Total PnL": 0, "Report": f"No signals from {start_date} to {end_date}"}
    
    os.makedirs('reports', exist_ok=True)
    trades_df.to_csv('reports/backtest_report.csv', index=False)
    
    return {
        "Total Trades": len(trades_df) // 2,
        "Total PnL": round(trades_df['PnL (Points)'].sum(), 2),
        "Report": f"Data from {start_date} to {end_date} generated."
    }



