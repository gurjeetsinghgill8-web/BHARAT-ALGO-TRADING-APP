import sys
import os
import pandas as pd
from datetime import datetime

# Add current dir to path so we can import crypto_backtester
sys.path.append(os.getcwd())
import crypto_backtester

print("Fetching 12 months of 1H data and running backtest...")
try:
    res = crypto_backtester.run_crypto_backtest(
        asset_ticker="BTC-USD",
        days=365,
        timeframe="1 Hour",
        st_period=10,
        st_mult=1.5,
        otm_strikes=5,
        simulated_premium=200.0,
        brokerage_per_trade=2.0
    )
    
    if "error" in res:
        print(f"Error: {res['error']}")
    else:
        trades_df = res["Trades"]
        
        # Convert Exit Time to datetime
        trades_df['Exit Time'] = pd.to_datetime(trades_df['Exit Time'])
        
        # Add Month column (YYYY-MM)
        trades_df['Month'] = trades_df['Exit Time'].dt.to_period('M')
        
        # Group by Month
        monthly = trades_df.groupby('Month').agg(
            Trades=('Net P&L', 'count'),
            Win_Trades=('Net P&L', lambda x: (x > 0).sum()),
            Net_PnL=('Net P&L', 'sum')
        ).reset_index()
        
        monthly['Win Rate %'] = round((monthly['Win_Trades'] / monthly['Trades']) * 100, 1)
        
        # Assume a starting capital of $1000 for ROI calculation
        CAPITAL = 1000.0
        monthly['ROI % (on $1k)'] = round((monthly['Net_PnL'] / CAPITAL) * 100, 2)
        
        # Format the PnL column
        monthly['Net_PnL'] = monthly['Net_PnL'].apply(lambda x: f"${x:,.2f}")
        
        print("\n=== 12-MONTH MONTHLY REPORT: BTC-USD (1H | 10, 1.5) ===")
        print(f"Assumed Deployed Capital: ${CAPITAL}")
        print("-" * 65)
        print(monthly[['Month', 'Trades', 'Win Rate %', 'Net_PnL', 'ROI % (on $1k)']].to_string(index=False))
        
        total_pnl = res['Total Net P&L ($)']
        total_roi = round((total_pnl / CAPITAL) * 100, 2)
        print("-" * 65)
        print(f"TOTAL ANNUAL P&L: ${total_pnl:,.2f}")
        print(f"TOTAL ANNUAL ROI: {total_roi}%")
        
except Exception as e:
    print(f"Error: {e}")
