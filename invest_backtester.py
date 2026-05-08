"""
invest_backtester.py — BHARAT ALGOVERSE v5.5 | THE MASTERSTROKE
================================================================
Strategy: Monthly BB Blast + Daily Supertrend Exit.
Multi-Timeframe Breakout System.
"""

import pandas as pd
import numpy as np
import yfinance as yf
import pandas_ta as ta
from datetime import datetime, timedelta
import invest_rs_engine as rs_engine
from utils import log_terminal

def get_indicators(ticker):
    """
    Fetches Monthly data for BB Blast and Daily data for Supertrend.
    Returns: (monthly_df, daily_df)
    """
    try:
        # Monthly for BB (last 2 years)
        m_df = yf.download(ticker, period="5y", interval="1mo", progress=False)
        # Daily for Supertrend (last 2 years)
        d_df = yf.download(ticker, period="2y", interval="1d", progress=False)
        
        if m_df.empty or d_df.empty:
            return None, None
            
        # Monthly Upper BB (20, 2)
        bb = ta.bbands(m_df['Close'], length=20, std=2)
        if bb is not None:
            m_df['bb_upper'] = bb['BBU_20_2.0']
        
        # Daily Supertrend (10, 2)
        st = ta.supertrend(d_df['High'], d_df['Low'], d_df['Close'], length=10, multiplier=2)
        if st is not None:
            d_df['st_val'] = st['SUPERT_10_2.0']
            d_df['st_dir'] = st['SUPERTd_10_2.0']
            
        return m_df, d_df
    except Exception as e:
        log_terminal(f"Indicator Error [{ticker}]: {e}", "ERROR")
        return None, None

def check_live_blast(ticker):
    """Checks if a stock is CURRENTLY in a BB Blast and above Daily ST."""
    m_df, d_df = get_indicators(ticker)
    if m_df is None or d_df is None: return False, "No Data"
    
    ltp = d_df['Close'].iloc[-1]
    monthly_upper_bb = m_df['bb_upper'].iloc[-1]
    daily_st = d_df['st_val'].iloc[-1]
    st_dir = d_df['st_dir'].iloc[-1]
    
    is_blast = ltp > monthly_upper_bb
    is_above_st = st_dir == 1 # 1 = Uptrend
    
    if is_blast and is_above_st:
        return True, "🚀 BLAST ACTIVE"
    elif is_blast:
        return False, "⚠️ BB Blast but below ST"
    elif is_above_st:
        return False, "📈 Above ST but no BB Blast"
    return False, "❄️ Cold"

def run_bb_backtest(tickers, start_date, end_date, initial_capital=100000):
    """
    Runs the Masterstroke simulation.
    """
    log_terminal(f"[BACKTEST] Running BB Blast Strategy on {len(tickers)} stocks...", "INFO")
    
    trades = []
    portfolio_value = initial_capital
    active_trades = {} # ticker -> {entry_price, entry_date, units}
    
    # In a real backtest we'd iterate day-by-day, but for speed we'll do a simplified scan
    # For each ticker, find its BB Blast entry points and ST exit points
    for ticker in tickers:
        m_df, d_df = get_indicators(ticker)
        if m_df is None or d_df is None: continue
        
        # Merge Monthly BB onto Daily data for precise entry check
        # We assume entry happens on the day price crosses Monthly BB
        d_df = d_df.sort_index()
        m_df = m_df.sort_index()
        
        # Logic: Find days where Daily Close > Monthly Upper BB (from previous month)
        # and Daily ST Dir is 1.
        
        # Simplified: Loop through daily data
        in_position = False
        entry_price = 0
        entry_date = None
        
        for i in range(1, len(d_df)):
            date = d_df.index[i]
            if date < pd.Timestamp(start_date) or date > pd.Timestamp(end_date): continue
            
            close = d_df['Close'].iloc[i]
            st_dir = d_df['st_dir'].iloc[i]
            
            # Get BB from the start of the current month
            month_start = date.replace(day=1)
            if month_start in m_df.index:
                bb_upper = m_df.loc[month_start, 'bb_upper']
            else:
                # Find previous available month
                prev_months = m_df.index[m_df.index < month_start]
                if not prev_months.empty:
                    bb_upper = m_df.loc[prev_months[-1], 'bb_upper']
                else:
                    continue

            if not in_position:
                # ENTRY CONDITION
                if close > bb_upper and st_dir == 1:
                    in_position = True
                    entry_price = close
                    entry_date = date
            else:
                # EXIT CONDITION
                if st_dir == -1: # Supertrend Flip
                    in_position = False
                    exit_price = close
                    ret = (exit_price / entry_price - 1) * 100
                    trades.append({
                        "ticker": ticker,
                        "entry_date": entry_date.strftime("%Y-%m-%d"),
                        "exit_date": date.strftime("%Y-%m-%d"),
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(exit_price, 2),
                        "return_pct": round(ret, 2),
                        "days": (date - entry_date).days
                    })
    
    # Sort trades by entry date
    trades.sort(key=lambda x: x["entry_date"])
    
    # Stats
    if not trades:
        return {"summary": {"total_trades": 0}, "trades": []}
        
    wins = [t for t in trades if t["return_pct"] > 0]
    win_rate = len(wins) / len(trades) * 100
    avg_ret = np.mean([t["return_pct"] for t in trades])
    max_ret = max([t["return_pct"] for t in trades])
    
    # Simple Portfolio Simulation (Assuming 10% allocation per trade)
    # Note: This is very basic, a real one would handle overlap.
    total_compounded = 100.0
    for t in trades:
        # Assuming we put 20% of current capital in each trade
        total_compounded *= (1 + (t["return_pct"] / 100) * 0.20)
        
    summary = {
        "total_trades": len(trades),
        "win_rate": round(win_rate, 2),
        "avg_return": round(avg_ret, 2),
        "max_profit": round(max_ret, 2),
        "portfolio_growth": round(total_compounded - 100, 2),
        "final_value": round(initial_capital * (total_compounded / 100), 2)
    }
    
    return {"summary": summary, "trades": trades}

if __name__ == "__main__":
    # Test
    res = run_bb_backtest(["HAL.NS", "BEL.NS", "TATAMOTORS.NS"], "2024-01-01", "2026-05-01")
    print(res["summary"])
