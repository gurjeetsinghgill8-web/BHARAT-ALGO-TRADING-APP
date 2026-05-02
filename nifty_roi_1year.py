import pandas as pd
import yfinance as yf
import numpy as np
import datetime
import logic
import os

def run_nifty_backtest():
    print("="*60)
    print("      NIFTY 1-YEAR ROI REPORT (GILL 120 STRATEGY)      ")
    print("="*60)
    
    # 1. Fetch Data
    symbol = "^NSEI"
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365)
    
    print(f"Fetching 1 year of data for {symbol}...")
    df = yf.download(symbol, start=start_date, end=end_date, interval="1h")
    
    if df.empty:
        print("Error: Could not fetch data.")
        return

    # Flatten columns if multi-indexed
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df.columns = [c.lower() for c in df.columns]
    
    # 2. Calculate Supertrend (10, 1.5 as per Aggressive SAR defaults)
    period = 10
    multiplier = 1.5
    df = logic.calculate_supertrend(df, period=period, multiplier=multiplier)
    
    dir_col = f"SUPERTd_{period}_{multiplier}"
    
    # 3. Simulate SAR Trades
    trades = []
    current_pos = 0 # 0: none, 1: long (CE), -1: short (PE)
    entry_price = 0
    entry_time = None
    
    # Strategy parameters
    premium_entry = 120.0
    lot_size = 50
    capital_per_trade = premium_entry * lot_size # Rs. 6000
    
    for i in range(1, len(df)):
        prev_dir = df[dir_col].iloc[i-1]
        curr_dir = df[dir_col].iloc[i]
        curr_price = df['close'].iloc[i]
        curr_time = df.index[i]
        
        # SAR Flip: SELL to BUY
        if prev_dir == -1 and curr_dir == 1:
            if current_pos == -1:
                # Close short
                exit_price = curr_price
                pnl_pts = entry_price - exit_price # Short pnl
                # Simple approximation: 1 point in spot = 0.5 point in option (delta 0.5)
                opt_pnl = pnl_pts * 0.5 
                trades.append({
                    'type': 'PE',
                    'entry_time': entry_time,
                    'exit_time': curr_time,
                    'entry_spot': entry_price,
                    'exit_spot': exit_price,
                    'pnl_pts': opt_pnl,
                    'pnl_rs': opt_pnl * lot_size
                })
            
            # Open long
            current_pos = 1
            entry_price = curr_price
            entry_time = curr_time
            
        # SAR Flip: BUY to SELL
        elif prev_dir == 1 and curr_dir == -1:
            if current_pos == 1:
                # Close long
                exit_price = curr_price
                pnl_pts = exit_price - entry_price
                opt_pnl = pnl_pts * 0.5
                trades.append({
                    'type': 'CE',
                    'entry_time': entry_time,
                    'exit_time': curr_time,
                    'entry_spot': entry_price,
                    'exit_spot': exit_price,
                    'pnl_pts': opt_pnl,
                    'pnl_rs': opt_pnl * lot_size
                })
            
            # Open short
            current_pos = -1
            entry_price = curr_price
            entry_time = curr_time

    # 4. Results
    if not trades:
        print("No trades generated.")
        return

    report_df = pd.DataFrame(trades)
    total_pnl = report_df['pnl_rs'].sum()
    win_rate = (report_df['pnl_rs'] > 0).mean() * 100
    total_trades = len(report_df)
    
    print("-" * 60)
    print(f"Total Trades: {total_trades}")
    print(f"Total Profit: Rs. {total_pnl:,.2f}")
    print(f"Win Rate    : {win_rate:.1f}%")
    print(f"Avg Profit/Trade: Rs. {total_pnl/total_trades:,.2f}")
    print(f"Est. ROI    : {(total_pnl/capital_per_trade)*100:.1f}% (on Rs.{capital_per_trade} capital)")
    print("-" * 60)
    
    # Save to CSV
    os.makedirs('reports', exist_ok=True)
    report_df.to_csv('reports/nifty_roi_1year.csv', index=False)
    print(f"Detailed report saved to reports/nifty_roi_1year.csv")

if __name__ == "__main__":
    run_nifty_backtest()
