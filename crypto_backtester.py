"""
crypto_backtester.py - Realistic Crypto Backtest
=================================================
Key Fix: Uses 4H candles (not 1H) so Supertrend doesn't flip every hour.
This matches how you actually trade - hold for DAYS, exit only on real trend flip.
"""

import pandas as pd
import numpy as np
import yfinance as yf
import logic
import db
import os
from datetime import datetime


def fetch_crypto_data(asset_ticker, days):
    """
    Fetches BTC-USD or ETH-USD using 4H candles.
    4H = fewer, higher-quality signals. Matches real trading style.
    """
    # ALWAYS use Daily candles - matches real trading (hold 3-7 days per trade)
    interval = "1d"
    print(f"[CryptoLab] Downloading {asset_ticker} | {days}d | DAILY candles (real trading style)...")

    try:
        df = yf.download(asset_ticker, period=f"{days}d", interval=interval, progress=False)
        if df.empty:
            raise Exception("Empty data.")

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]
        return df
    except Exception as e:
        print(f"[CryptoLab] Fetch Error: {e}")
        return pd.DataFrame()


def run_crypto_backtest(asset_ticker="BTC-USD", days=30, otm_strikes=5, simulated_premium=200.0):
    """
    Realistic backtest:
    - 4H candles (or 1D for long range) = hold positions for days not hours
    - Exit only when Supertrend GENUINELY flips
    - P&L based on actual spot move captured

    Deep OTM BTC Options (5 strikes out):
    - Typical strike interval: $1000 (so 5 OTM = $5000 away from spot)
    - Delta ~ 0.08-0.15 for 5-strike OTM
    - Wins happen when BTC moves $2000+ in your direction

    Premium simulation:
    - We pay `simulated_premium` at entry
    - At exit: if move in right direction > break-even, we profit
    - Break-even = premium / delta = $200 / 0.10 = $2000 BTC move
    """
    df = fetch_crypto_data(asset_ticker, days)
    if df.empty:
        return {"error": "Could not fetch data."}

    # Store OTM strikes setting
    db.set_param('crypto_otm_strikes', otm_strikes)

    df_st = logic.calculate_supertrend(df)
    period = int(float(db.get_param('st_period', 10)))
    multiplier = float(db.get_param('st_multiplier', 1.5))
    dir_col = f"SUPERTd_{period}_{multiplier}"

    if dir_col not in df_st.columns:
        return {"error": "Supertrend calculation failed."}

    df_st['prev_dir'] = df_st[dir_col].shift(1)

    trades = []
    current_pos = None
    entry_spot = 0.0
    entry_time = None

    delta_estimate = 0.15  # Deep OTM delta 5-strikes: ~0.10-0.20, use 0.15 for daily moves

    for idx, row in df_st.dropna(subset=[dir_col, 'prev_dir']).iterrows():
        prev_dir = row['prev_dir']
        last_dir = row[dir_col]

        signal = None
        if prev_dir == -1 and last_dir == 1:
            signal = "BUY CE"
        elif prev_dir == 1 and last_dir == -1:
            signal = "BUY PE"

        if signal and signal != current_pos:
            # ── Exit old position
            if current_pos:
                exit_spot = round(float(row['close']), 2)
                spot_move = exit_spot - entry_spot
                hold_candles = len(df_st.loc[entry_time:idx]) if entry_time else 0
                hold_days = hold_candles  # On 1D candles, each candle = 1 day

                # P&L calculation
                if "CE" in current_pos:
                    if spot_move > 0:
                        # Moved in right direction
                        option_pnl = round((spot_move * delta_estimate) - simulated_premium, 2)
                    else:
                        option_pnl = round(-simulated_premium, 2)
                else:  # PE
                    if spot_move < 0:
                        option_pnl = round((abs(spot_move) * delta_estimate) - simulated_premium, 2)
                    else:
                        option_pnl = round(-simulated_premium, 2)

                trades.append({
                    "Date": idx.strftime("%Y-%m-%d"),
                    "Action": f"EXIT {current_pos}",
                    "Spot ($)": exit_spot,
                    "BTC Move ($)": round(spot_move, 2),
                    "Days Held": hold_days,
                    "P&L ($)": option_pnl
                })

            # ── Enter new position
            current_pos = signal
            entry_spot = round(float(row['close']), 2)
            entry_time = idx
            trades.append({
                "Date": idx.strftime("%Y-%m-%d"),
                "Action": f"ENTRY {current_pos} [5 OTM]",
                "Spot ($)": entry_spot,
                "BTC Move ($)": 0.0,
                "Days Held": 0,
                "P&L ($)": 0.0
            })

    trades_df = pd.DataFrame(trades)

    if trades_df.empty:
        return {"error": "No signals generated. Try a longer period."}

    exits = trades_df[trades_df['P&L ($)'] != 0.0]
    total_pnl = round(exits['P&L ($)'].sum(), 2)
    wins = len(exits[exits['P&L ($)'] > 0])
    losses = len(exits[exits['P&L ($)'] <= 0])
    win_rate = round(wins / len(exits) * 100, 1) if len(exits) > 0 else 0

    os.makedirs('reports', exist_ok=True)
    filename = f"reports/crypto_{asset_ticker.replace('-','_')}_{days}d.csv"
    trades_df.to_csv(filename, index=False)

    return {
        "Asset": asset_ticker,
        "Period": f"{days} days",
        "Candle": "1D (Daily - Real trading style)",
        "Total Signals": len(exits),
        "Wins": wins,
        "Losses": losses,
        "Win Rate (%)": win_rate,
        "Total P&L ($)": total_pnl,
        "Break-even Move Needed": f"${simulated_premium / delta_estimate:,.0f}",
        "Report File": filename,
        "Data": trades_df
    }
