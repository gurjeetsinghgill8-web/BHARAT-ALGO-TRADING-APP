import sys
import os
import pandas as pd
from datetime import datetime

# Add current dir to path so we can import crypto_backtester
sys.path.append(os.getcwd())
import crypto_backtester

# Timeframes and parameters to test
timeframes = ["15 Min", "30 Min", "1 Hour"]
periods = [10]
multipliers = [1.0, 1.5, 2.0]

print("Fetching 60 days of data (Max limit for 15m/30m on Yahoo Finance) for ATM/Slight ITM...")

results = []

for tf in timeframes:
    for p in periods:
        for m in multipliers:
            config_name = f"{tf} | ({p}, {m})"
            print(f"Testing {config_name}...")
            try:
                # Using 3 Days ATM parameters: delta=0.55, premium=$500
                res = crypto_backtester.run_crypto_backtest(
                    asset_ticker="BTC-USD",
                    days=60,
                    timeframe=tf,
                    st_period=p,
                    st_mult=m,
                    otm_strikes=0, # ATM
                    simulated_premium=500.0,
                    brokerage_per_trade=2.0,
                    delta_estimate=0.55
                )
                
                if "error" not in res and res.get("Total Trades", 0) > 0:
                    results.append({
                        "Config": config_name,
                        "Timeframe": tf,
                        "Multiplier": m,
                        "Total Trades": res["Total Trades"],
                        "Win Rate %": res["Win Rate (%)"],
                        "60-Day P&L": res['Total Net P&L ($)']
                    })
            except Exception as e:
                print(f"Error on {config_name}: {e}")

print("\n=== 60-DAY OPTIMIZATION RESULTS (ATM/ITM - 3 Days Expiry) ===")
if results:
    df = pd.DataFrame(results)
    df = df.sort_values(by="60-Day P&L", ascending=False)
    print(df.to_string(index=False))
else:
    print("No valid trades found.")

# SUPREME CLOUD SYNC: 2026-04-30
