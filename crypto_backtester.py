"""
crypto_backtester.py - Fixed P&L Advanced Crypto Backtester
===========================================================
Features:
- Fixed P&L: P&L = (Spot Move * Delta * Direction)
- Flexible Timeframes (15m, 1h, 4h, 1d)
- Custom Supertrend Parameters
- Detailed Brokerage & Net P&L Tracking
"""

import pandas as pd
import numpy as np
import yfinance as yf
import logic
import db
import os
from datetime import datetime

def fetch_crypto_data(asset_ticker, days, timeframe):
    interval_map = {
        "15 Min": "15m",
        "30 Min": "30m",
        "1 Hour": "1h",
        "4 Hour": "4h",
        "1 Day": "1d"
    }
    interval = interval_map.get(timeframe, "1h")
    print(f"[CryptoLab] Downloading {asset_ticker} | {days}d | {interval} candles...")
    try:
        df = yf.download(asset_ticker, period=f"{days}d", interval=interval, progress=False)
        if df.empty: raise Exception("Empty data.")
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]
        return df
    except Exception as e:
        print(f"[CryptoLab] Fetch Error: {e}")
        return pd.DataFrame()

def run_crypto_backtest(asset_ticker="BTC-USD", days=30, timeframe="1 Hour", 
                        st_period=10, st_mult=1.5, otm_strikes=5, 
                        simulated_premium=200.0, brokerage_per_trade=2.0):
    df = fetch_crypto_data(asset_ticker, days, timeframe)
    if df.empty: return {"error": "Could not fetch data."}

    df_st = logic.calculate_supertrend(df, period=st_period, multiplier=st_mult)
    dir_col = f"SUPERTd_{st_period}_{st_mult}"
    if dir_col not in df_st.columns: return {"error": "Supertrend failed."}

    df_st['prev_dir'] = df_st[dir_col].shift(1)
    trades = []
    current_pos = None
    entry_spot = 0.0
    entry_time = None
    delta_estimate = 0.15 

    for idx, row in df_st.dropna(subset=[dir_col, 'prev_dir']).iterrows():
        prev_dir = row['prev_dir']
        last_dir = row[dir_col]
        signal = None
        if prev_dir == -1 and last_dir == 1: signal = "BUY CE"
        elif prev_dir == 1 and last_dir == -1: signal = "BUY PE"

        if signal and signal != current_pos:
            if current_pos:
                exit_spot = round(float(row['close']), 2)
                spot_move = exit_spot - entry_spot
                
                # CORRECT LOGIC:
                # Option P&L = (Spot Change) * Delta * Direction
                if "CE" in current_pos:
                    realized_pnl = round(spot_move * delta_estimate, 2)
                else: # PE
                    realized_pnl = round(-spot_move * delta_estimate, 2)
                
                # Cannot lose more than the premium paid
                if realized_pnl < -simulated_premium:
                    realized_pnl = -simulated_premium
                
                net_pnl = round(realized_pnl - (brokerage_per_trade * 2), 2)

                trades.append({
                    "Entry Time": entry_time.strftime("%Y-%m-%d %H:%M"),
                    "Exit Time": idx.strftime("%Y-%m-%d %H:%M"),
                    "Type": current_pos,
                    "Entry Spot": entry_spot,
                    "Exit Spot": exit_spot,
                    "Spot Move": round(spot_move, 2),
                    "Realized P&L": realized_pnl,
                    "Brokerage": brokerage_per_trade * 2,
                    "Net P&L": net_pnl
                })

            current_pos = signal
            entry_spot = round(float(row['close']), 2)
            entry_time = idx

    trades_df = pd.DataFrame(trades)
    if trades_df.empty: return {"error": "No flips detected."}

    total_realized = round(trades_df['Realized P&L'].sum(), 2)
    total_brokerage = round(trades_df['Brokerage'].sum(), 2)
    total_net = round(trades_df['Net P&L'].sum(), 2)
    wins = len(trades_df[trades_df['Net P&L'] > 0])
    losses = len(trades_df[trades_df['Net P&L'] <= 0])
    win_rate = round(wins / len(trades_df) * 100, 1)

    os.makedirs('reports', exist_ok=True)
    filename = f"reports/detailed_crypto_{asset_ticker.replace('-','_')}.csv"
    trades_df.to_csv(filename, index=False)

    return {
        "Asset": asset_ticker,
        "Timeframe": timeframe,
        "ST Params": f"({st_period}, {st_mult})",
        "Total Trades": len(trades_df),
        "Wins": wins,
        "Losses": losses,
        "Win Rate (%)": win_rate,
        "Total Realized ($)": total_realized,
        "Total Brokerage ($)": total_brokerage,
        "Total Net P&L ($)": total_net,
        "Report File": filename,
        "Trades": trades_df,
        "Equity Curve": trades_df['Net P&L'].cumsum()
    }
