"""
crypto_backtester.py - Advanced Crypto Backtester (Fixed Logic)
=============================================================
Matches TradingView behavior. Detailed trade logging.
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
    try:
        df = yf.download(asset_ticker, period=f"{days}d", interval=interval, progress=False)
        if df.empty: return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]
        return df
    except:
        return pd.DataFrame()

def run_crypto_backtest(asset_ticker="BTC-USD", days=30, timeframe="1 Hour", 
                        st_period=10, st_mult=1.0, otm_strikes=5, 
                        simulated_premium=200.0, brokerage_per_trade=2.0):
    df = fetch_crypto_data(asset_ticker, days, timeframe)
    if df.empty: return {"error": "No data found."}

    df_st = logic.calculate_supertrend(df, period=st_period, multiplier=st_mult)
    st_val_col = f"SUPERT_{st_period}_{st_mult}"
    dir_col    = f"SUPERTd_{st_period}_{st_mult}"

    df_st['prev_dir'] = df_st[dir_col].shift(1)
    trades = []
    current_pos = None
    entry_spot = 0.0
    entry_time = None
    delta_estimate = 0.15 

    for idx, row in df_st.dropna(subset=[dir_col, 'prev_dir']).iterrows():
        prev_dir = row['prev_dir']
        last_dir = row[dir_col]
        
        # Only flip when direction actually CHANGES
        signal = None
        if prev_dir == -1 and last_dir == 1: signal = "BUY CE"
        elif prev_dir == 1 and last_dir == -1: signal = "BUY PE"

        if signal and signal != current_pos:
            if current_pos:
                exit_spot = round(float(row['close']), 2)
                spot_move = exit_spot - entry_spot
                
                if "CE" in current_pos:
                    realized_pnl = round(spot_move * delta_estimate, 2)
                else:
                    realized_pnl = round(-spot_move * delta_estimate, 2)
                
                if realized_pnl < -simulated_premium: realized_pnl = -simulated_premium
                net_pnl = round(realized_pnl - (brokerage_per_trade * 2), 2)

                trades.append({
                    "Entry Time": entry_time.strftime("%Y-%m-%d %H:%M"),
                    "Exit Time": idx.strftime("%Y-%m-%d %H:%M"),
                    "Type": current_pos,
                    "Entry Spot": entry_spot,
                    "Exit Spot": exit_spot,
                    "ST Line": round(float(row[st_val_col]), 2),
                    "Spot Move": round(spot_move, 2),
                    "Realized P&L": realized_pnl,
                    "Net P&L": net_pnl
                })

            current_pos = signal
            entry_spot = round(float(row['close']), 2)
            entry_time = idx

    trades_df = pd.DataFrame(trades)
    if trades_df.empty: return {"error": "No flips detected in this period."}

    return {
        "Asset": asset_ticker,
        "Timeframe": timeframe,
        "ST Params": f"({st_period}, {st_mult})",
        "Total Trades": len(trades_df),
        "Total Realized ($)": round(trades_df['Realized P&L'].sum(), 2),
        "Total Brokerage ($)": round(len(trades_df) * brokerage_per_trade * 2, 2),
        "Total Net P&L ($)": round(trades_df['Net P&L'].sum(), 2),
        "Win Rate (%)": round(len(trades_df[trades_df['Net P&L'] > 0]) / len(trades_df) * 100, 1),
        "Trades": trades_df,
        "Equity Curve": trades_df['Net P&L'].cumsum(),
        "Report File": "reports/crypto_latest.csv"
    }
