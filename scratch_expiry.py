import sys
import os
import pandas as pd
from datetime import datetime

# Add current dir to path so we can import crypto_backtester
sys.path.append(os.getcwd())
import crypto_backtester

# Configurations for ATM / Slight ITM at different expirations
expirations = [
    {"name": "3 Days Away (ATM/ITM)", "delta": 0.55, "premium": 500.0},
    {"name": "7 Days Away (ATM/ITM)", "delta": 0.55, "premium": 1000.0},
    {"name": "1 Month Away (ATM/ITM)", "delta": 0.60, "premium": 2000.0},
    {"name": "2 Months Away (ATM/ITM)", "delta": 0.65, "premium": 3500.0}
]

print("Fetching 12 months of 1H data for Expiry Optimization (ATM / Slight ITM)...")

results = []

for exp in expirations:
    print(f"Testing {exp['name']}...")
    try:
        res = crypto_backtester.run_crypto_backtest(
            asset_ticker="BTC-USD",
            days=365,
            timeframe="1 Hour",
            st_period=10,
            st_mult=1.5,
            otm_strikes=3,
            simulated_premium=exp['premium'],
            brokerage_per_trade=2.0,
            delta_estimate=exp['delta']
        )
        
        if "error" not in res:
            trades_df = res["Trades"]
            trades_df['Exit Time'] = pd.to_datetime(trades_df['Exit Time'])
            trades_df['Month'] = trades_df['Exit Time'].dt.to_period('M')
            
            monthly = trades_df.groupby('Month')['Net P&L'].sum().reset_index()
            monthly['Expiry'] = exp['name']
            
            # Assume 10x max premium as starting capital for ROI
            # But let's just do absolute ROI based on $2000 standard capital to compare apples to apples
            capital = 2000.0
            
            # Record total stats
            results.append({
                "Expiry": exp['name'],
                "Delta (Speed)": exp['delta'],
                "Max Loss Cap": f"${exp['premium']}",
                "Total Trades": len(trades_df),
                "Win Rate %": res["Win Rate (%)"],
                "Annual P&L": res['Total Net P&L ($)'],
                "Annual ROI (on $2k)": f"{(res['Total Net P&L ($)'] / capital * 100):.1f}%",
                "Monthly_Data": monthly
            })
            
    except Exception as e:
        print(f"Error on {exp['name']}: {e}")

# Compile 12-month tabular data
print("\n=== EXPIRY OPTIMIZATION RESULTS (1 Hour | 10, 1.5) ===")
summary_df = pd.DataFrame([
    {k: v for k, v in r.items() if k != "Monthly_Data"} 
    for r in results
])
print(summary_df.to_string(index=False))

print("\n=== 12-MONTH MONTHLY P&L COMPARISON (ATM/ITM) ===")
# Pivot table for months
all_monthly = pd.concat([r['Monthly_Data'] for r in results])
pivot_df = all_monthly.pivot(index='Month', columns='Expiry', values='Net P&L').fillna(0)
pivot_df = pivot_df[['3 Days Away (ATM/ITM)', '7 Days Away (ATM/ITM)', '1 Month Away (ATM/ITM)', '2 Months Away (ATM/ITM)']] # Ordered
for col in pivot_df.columns:
    pivot_df[col] = pivot_df[col].apply(lambda x: f"${x:,.2f}")
print(pivot_df.to_string())


# SUPREME CLOUD SYNC: 2026-04-30
