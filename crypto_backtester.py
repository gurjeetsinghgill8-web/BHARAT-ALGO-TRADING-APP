"""
crypto_backtester.py - Crypto History Lab
==========================================
Backtests the "Gill Crypto Rule" on BTC/ETH historical spot data.
- Supertrend (10, 1.5) flips = Signal
- Simulates 5-strike OTM entry with fixed $X premium per contract
- Periods: 1 Month, 1 Quarter, 1 Year
- All times shown in UTC (Crypto is global, no IST filter)
"""

import pandas as pd
import yfinance as yf
import logic
import db
import os
from datetime import datetime


def fetch_crypto_data(asset_ticker, days):
    """
    Fetches BTC-USD or ETH-USD historical data from Yahoo Finance.
    Uses 1h interval (best balance of detail + availability).
    """
    print(f"[CryptoLab] Downloading {asset_ticker} | {days}d | 1h ...")
    try:
        df = yf.download(asset_ticker, period=f"{days}d", interval="1h", progress=False)
        if df.empty:
            raise Exception("Empty data from Yahoo Finance.")

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        print(f"[CryptoLab] Fetch Error: {e}")
        return pd.DataFrame()


def run_crypto_backtest(asset_ticker="BTC-USD", days=30, otm_strikes=5, simulated_premium=200.0):
    """
    Runs the 'Gill Crypto Rule' backtest.

    Args:
        asset_ticker: 'BTC-USD' or 'ETH-USD'
        days: Lookback period in days (30, 90, 365)
        otm_strikes: How many strikes OTM (default 5)
        simulated_premium: Simulated option buy price in USD (e.g., $200)

    Since we can't get historical option chain data for free,
    we simulate premium capture as:
        - Entry: Pay `simulated_premium` per contract
        - Exit on flip: Spot move * delta_estimate (0.15 for deep OTM)

    Returns: dict with metrics + trades DataFrame
    """
    df = fetch_crypto_data(asset_ticker, days)
    if df.empty:
        return {"error": "Could not fetch data."}

    # Calculate Supertrend
    df_st = logic.calculate_supertrend(df)
    dir_col = f"SUPERTd_{int(db.get_param('st_period', 10))}_{float(db.get_param('st_multiplier', 1.5))}"

    if dir_col not in df_st.columns:
        return {"error": "Supertrend calculation failed."}

    df_st['prev_dir'] = df_st[dir_col].shift(1)

    trades = []
    current_pos = None
    entry_spot = 0.0
    entry_time = None

    # Deep OTM delta approximation (realistic for 5+ strikes OTM)
    delta_estimate = 0.10  # ~10 cents move per $1 spot move for deep OTM

    for idx, row in df_st.dropna(subset=[dir_col, 'prev_dir']).iterrows():
        prev_dir = row['prev_dir']
        last_dir = row[dir_col]

        signal = None
        if prev_dir == -1 and last_dir == 1:
            signal = "BUY CE"
        elif prev_dir == 1 and last_dir == -1:
            signal = "BUY PE"

        if signal and signal != current_pos:
            # Exit old position
            if current_pos:
                exit_spot = round(float(row['close']), 2)
                spot_move = abs(exit_spot - entry_spot)

                # Estimate option profit
                if "CE" in current_pos and exit_spot > entry_spot:
                    option_pnl = round((spot_move * delta_estimate) - simulated_premium, 2)
                elif "PE" in current_pos and exit_spot < entry_spot:
                    option_pnl = round((spot_move * delta_estimate) - simulated_premium, 2)
                else:
                    option_pnl = round(-simulated_premium, 2)  # Full loss (expired OTM)

                trades.append({
                    "Time (UTC)": idx.strftime("%Y-%m-%d %H:%M"),
                    "Action": f"SQUARE OFF {current_pos}",
                    "Spot Price ($)": exit_spot,
                    "Spot Move ($)": round(spot_move, 2),
                    "Option P&L ($)": option_pnl
                })

            # Enter new position
            current_pos = signal
            entry_spot = round(float(row['close']), 2)
            entry_time = idx

            trades.append({
                "Time (UTC)": idx.strftime("%Y-%m-%d %H:%M"),
                "Action": f"ENTRY {current_pos} (5 OTM)",
                "Spot Price ($)": entry_spot,
                "Spot Move ($)": 0.0,
                "Option P&L ($)": 0.0
            })

    trades_df = pd.DataFrame(trades)

    if trades_df.empty:
        return {"Total Trades": 0, "Total PnL ($)": 0, "Report": "No signals found."}

    # Save report
    os.makedirs('reports', exist_ok=True)
    filename = f"reports/crypto_backtest_{asset_ticker.replace('-','_')}_{days}d.csv"
    trades_df.to_csv(filename, index=False)

    exits = trades_df[trades_df['Option P&L ($)'] != 0.0]
    total_pnl = round(exits['Option P&L ($)'].sum(), 2)
    wins = len(exits[exits['Option P&L ($)'] > 0])
    win_rate = round(wins / len(exits) * 100, 1) if len(exits) > 0 else 0

    return {
        "Asset": asset_ticker,
        "Period": f"{days} days",
        "Total Trades": len(exits),
        "Win Rate (%)": win_rate,
        "Total P&L ($)": total_pnl,
        "Report File": filename,
        "Data": trades_df
    }
