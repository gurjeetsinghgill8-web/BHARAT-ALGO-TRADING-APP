"""
crypto_backtester.py - HYBRID KING Backtester
==============================================
Supports both modes:
  mode="hybrid_king" → ADX + RSI + Supertrend (lowest drawdown)
  mode="adx_only"    → ADX + Supertrend (max profit)
  mode="plain"       → Plain Supertrend only
"""

import pandas as pd
import numpy as np
import yfinance as yf
import logic
import db
import os

def fetch_crypto_data(asset_ticker, days, timeframe):
    interval_map = {
        "15 Min": "15m", "30 Min": "30m",
        "1 Hour": "1h", "4 Hour": "4h", "1 Day": "1d"
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
                        st_period=10, st_mult=1.5, otm_strikes=0, 
                        simulated_premium=500.0, brokerage_per_trade=2.0, 
                        delta_estimate=0.55, mode="hybrid_king"):
    df = fetch_crypto_data(asset_ticker, days, timeframe)
    if df.empty: return {"error": "No data found."}

    # Calculate all indicators
    df = logic.calculate_supertrend(df, period=st_period, multiplier=st_mult)
    st_val_col = f"SUPERT_{st_period}_{st_mult}"
    dir_col    = f"SUPERTd_{st_period}_{st_mult}"
    
    df['adx'] = logic.calculate_adx(df, 14)
    df['rsi'] = logic.calculate_rsi(df['close'], 14)
    df['prev_dir'] = df[dir_col].shift(1)

    trades = []
    current_pos = None
    entry_spot = 0.0
    entry_st_line = 0.0
    entry_time = None

    for idx, row in df.dropna(subset=[dir_col, 'prev_dir']).iterrows():
        prev_dir = row['prev_dir']
        last_dir = row[dir_col]
        current_st_line = round(float(row[st_val_col]), 2)
        adx_val = row['adx'] if not pd.isna(row['adx']) else 0
        rsi_val = row['rsi'] if not pd.isna(row['rsi']) else 50
        
        signal = None
        
        if mode == "hybrid_king":
            # HYBRID KING: ST flip + ADX > 25 + RSI confirmation
            if prev_dir == -1 and last_dir == 1 and adx_val >= 25 and rsi_val < 65:
                signal = "BUY CE"
            elif prev_dir == 1 and last_dir == -1 and adx_val >= 25 and rsi_val > 35:
                signal = "BUY PE"
        elif mode == "adx_only":
            # ADX FILTER: ST flip + ADX > 25
            if prev_dir == -1 and last_dir == 1 and adx_val >= 25:
                signal = "BUY CE"
            elif prev_dir == 1 and last_dir == -1 and adx_val >= 25:
                signal = "BUY PE"
        else:
            # PLAIN: Just ST flip
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
                    "Entry ST": entry_st_line,
                    "Exit Spot": exit_spot,
                    "Exit ST": current_st_line,
                    "ADX": round(adx_val, 1),
                    "RSI": round(rsi_val, 1),
                    "Spot Move": round(spot_move, 2),
                    "Realized P&L": realized_pnl,
                    "Net P&L": net_pnl
                })

            current_pos = signal
            entry_spot = round(float(row['close']), 2)
            entry_st_line = current_st_line
            entry_time = idx

    trades_df = pd.DataFrame(trades)
    if trades_df.empty: return {"error": "No trades detected."}

    return {
        "Asset": asset_ticker,
        "Timeframe": timeframe,
        "Mode": mode.upper(),
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

# SUPREME CLOUD SYNC: 2026-04-30
