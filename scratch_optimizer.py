import sys
import os
import pandas as pd

# Add current dir to path so we can import crypto_backtester
sys.path.append(os.getcwd())
import crypto_backtester

timeframes = ["1 Hour", "4 Hour", "1 Day"]
periods = [10, 14, 20]
multipliers = [1.0, 1.5, 2.0, 3.0]

results = []

print("Running optimization for BTC-USD (90 days - Last Quarter)...")
for tf in timeframes:
    for p in periods:
        for m in multipliers:
            print(f"Testing {tf} | ({p}, {m})...")
            try:
                res = crypto_backtester.run_crypto_backtest(
                    asset_ticker="BTC-USD",
                    days=90,
                    timeframe=tf,
                    st_period=p,
                    st_mult=m,
                    otm_strikes=5,
                    simulated_premium=200.0,
                    brokerage_per_trade=2.0
                )
                if "error" not in res and res.get("Total Trades", 0) > 0:
                    results.append({
                        "Timeframe": tf,
                        "Period": p,
                        "Multiplier": m,
                        "Trades": res["Total Trades"],
                        "Win Rate %": res["Win Rate (%)"],
                        "Net P&L $": res["Total Net P&L ($)"]
                    })
            except Exception as e:
                print(f"Error on {tf} {p} {m}: {e}")

df = pd.DataFrame(results)
if not df.empty:
    df = df.sort_values(by="Net P&L $", ascending=False)
    print("\n=== TOP 5 MOST PROFITABLE STRATEGIES ===")
    print(df.head(5).to_string(index=False))
    
    print("\n=== YOUR 15M (14, 1.0) STRATEGY (For Comparison) ===")
    your_strat = df[(df["Timeframe"] == "15 Min") & (df["Period"] == 14) & (df["Multiplier"] == 1.0)]
    if not your_strat.empty:
        print(your_strat.to_string(index=False))
    else:
        print("Your strategy had no valid trades or resulted in error.")
else:
    print("No valid results found.")

# SUPREME CLOUD SYNC: 2026-04-30
