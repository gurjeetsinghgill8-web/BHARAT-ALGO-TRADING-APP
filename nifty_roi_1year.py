import yfinance as yf
import pandas as pd
import numpy as np
import logic
import datetime

def run_nifty_1year_roi(period, multiplier, timeframe, lot_size=65, capital_per_lot=70000):
    symbol = "^NSEI"
    # yfinance limit: 1h data available for 730 days. 15m only for 60 days.
    # We will use 1h for 1-year backtest.
    tf = "1h" if timeframe == "1h" else "1h" # Fallback to 1h for 1 year
    
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365)
    
    df = yf.download(symbol, start=start_date, end=end_date, interval=tf, progress=False)
    if df.empty:
        return None
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]

    df = logic.calculate_supertrend(df, period=period, multiplier=multiplier)
    
    df['month'] = df.index.strftime('%Y-%m')
    
    trades = []
    in_position = False
    entry_price = 0
    direction = 0
    entry_time = None
    
    dir_col = f"SUPERTd_{period}_{multiplier}"
    
    for i in range(2, len(df)):
        last_dir = df[dir_col].iloc[i-1]
        prev_dir = df[dir_col].iloc[i-2]
        price = df['close'].iloc[i]
        curr_time = df.index[i]
        
        # Signal Crossover
        if (prev_dir == -1 and last_dir == 1) or (prev_dir == 1 and last_dir == -1):
            if in_position:
                # Calculate Spot Move
                spot_move = (price - entry_price) if direction == 1 else (entry_price - price)
                # Estimate Option PNL (Delta 0.5 for ATM)
                option_pnl_pts = spot_move * 0.5
                # Total Cash PNL
                cash_pnl = option_pnl_pts * lot_size
                
                trades.append({
                    "exit_time": curr_time,
                    "month": entry_time.strftime('%Y-%m'),
                    "pnl": cash_pnl
                })
            
            entry_price = price
            direction = 1 if last_dir == 1 else -1
            entry_time = curr_time
            in_position = True
            
    if not trades:
        return None
        
    trades_df = pd.DataFrame(trades)
    monthly_stats = trades_df.groupby('month')['pnl'].sum().reset_index()
    monthly_stats['ROI_%'] = (monthly_stats['pnl'] / capital_per_lot) * 100
    
    return monthly_stats

def start_report():
    print(">>> NIFTY 1-YEAR ROI REPORT (ST 10/1, 1h) <<<")
    print("Lot Size: 65 | Capital: Rs. 70,000 per lot")
    print("-" * 50)
    
    report = run_nifty_1year_roi(10, 1, "1h")
    
    if report is not None:
        print(report.to_string(index=False))
        total_pnl = report['pnl'].sum()
        avg_roi = report['ROI_%'].mean()
        print("-" * 50)
        print(f"TOTAL 1-YEAR PNL: Rs. {total_pnl:,.2f}")
        print(f"AVERAGE MONTHLY ROI: {avg_roi:.2f}%")
        print(f"ESTIMATED YEARLY ROI: {avg_roi * 12:.2f}%")
    else:
        print("No trades found.")

if __name__ == "__main__":
    start_report()
