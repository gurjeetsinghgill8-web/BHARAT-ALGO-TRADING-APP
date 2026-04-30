import sys
import os
import pandas as pd
from datetime import datetime

# Add current dir to path so we can import crypto_backtester
sys.path.append(os.getcwd())
import crypto_backtester

print("Fetching 12 months of 1H data for Final Monthly ROI Calculation...")
try:
    res = crypto_backtester.run_crypto_backtest(
        asset_ticker="BTC-USD",
        days=365,
        timeframe="1 Hour",
        st_period=10,
        st_mult=1.5,
        otm_strikes=0,
        simulated_premium=500.0,
        brokerage_per_trade=2.0,
        delta_estimate=0.55
    )
    
    if "error" in res:
        print(f"Error: {res['error']}")
    else:
        trades_df = res["Trades"]
        trades_df['Exit Time'] = pd.to_datetime(trades_df['Exit Time'])
        trades_df['Month'] = trades_df['Exit Time'].dt.to_period('M')
        
        monthly = trades_df.groupby('Month').agg(
            Trades=('Net P&L', 'count'),
            Win_Trades=('Net P&L', lambda x: (x > 0).sum()),
            Net_PnL=('Net P&L', 'sum')
        ).reset_index()
        
        # Capital deployed to safely trade ATM options with $500 risk
        CAPITAL = 5000.0
        
        monthly['Monthly Return %'] = round((monthly['Net_PnL'] / CAPITAL) * 100, 2)
        monthly['Net_PnL_Str'] = monthly['Net_PnL'].apply(lambda x: f"${x:,.2f}")
        
        print("\n=== 12-MONTH ROI REPORT (1 Hour | 10, 1.5 | ATM) ===")
        print(f"Assumed Deployed Capital: ${CAPITAL}")
        print("-" * 65)
        
        for idx, row in monthly.iterrows():
            print(f"Month: {row['Month']} | Trades: {row['Trades']:2} | P&L: {row['Net_PnL_Str']:>10} | ROI: {row['Monthly Return %']:>6}%")
        
        total_pnl = res['Total Net P&L ($)']
        avg_monthly_roi = monthly['Monthly Return %'].mean()
        total_roi = round((total_pnl / CAPITAL) * 100, 2)
        
        print("-" * 65)
        print(f"TOTAL ANNUAL P&L: ${total_pnl:,.2f}")
        print(f"TOTAL ANNUAL ROI: {total_roi}%")
        print(f"AVERAGE MONTHLY ROI: {avg_monthly_roi:.2f}%")
        
except Exception as e:
    print(f"Error: {e}")

# SUPREME CLOUD SYNC: 2026-04-30
