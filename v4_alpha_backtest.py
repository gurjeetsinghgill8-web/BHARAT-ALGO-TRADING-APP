
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import json
import os
import invest_rs_engine as rs_engine
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Config V4.1 "THE ALPHA HUNTER" ──────────────────────────────
RS_PERIOD         = 55      
STOCK_RSI_EXIT    = 50      
SECTOR_RSI_EXIT   = 40      # Lower sector RSI exit to give stocks more room
STEP_DAYS         = 7       
STOCKS_PER_CAP    = 2       # 2L + 2M + 2S = 6 stocks

def _price_on(df: pd.DataFrame, ticker: str, target_date: pd.Timestamp) -> float | None:
    if ticker not in df.columns: return None
    series = df[ticker].dropna()
    avail  = series[series.index <= target_date]
    if avail.empty: return None
    return float(avail.iloc[-1])

def _calc_rs_on(df: pd.DataFrame, ticker: str, ref_ticker: str, target_date: pd.Timestamp, period: int = RS_PERIOD) -> float | None:
    old_date = target_date - timedelta(days=period)
    p_now  = _price_on(df, ticker, target_date)
    p_old  = _price_on(df, ticker, old_date)
    r_now  = _price_on(df, ref_ticker, target_date)
    r_old  = _price_on(df, ref_ticker, old_date)
    if any(v is None or v == 0 for v in [p_now, p_old, r_now, r_old]): return None
    return (p_now / p_old) / (r_now / r_old)

def _calc_rsi_on(df: pd.DataFrame, ticker: str, target_date: pd.Timestamp, period: int = 14) -> float | None:
    if ticker not in df.columns: return None
    series = df[ticker].dropna()
    series = series[series.index <= target_date].tail(period * 3)
    if len(series) < period + 5: return None
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)

def run_v4_backtest(df, start_date: date, end_date: date, capital: float, max_sectors: int):
    # 2. State
    current_capital = float(capital)
    active_positions = {} # sec_name -> {entry_date, stocks: [{ticker, entry_price}], capital_allocated}
    portfolio_curve = []
    
    step_dates = []
    curr = start_date
    while curr <= end_date:
        step_dates.append(pd.Timestamp(curr))
        curr += timedelta(days=STEP_DAYS)

    for dt in step_dates:
        # A. Update Active Positions (Exits)
        secs_to_exit = []
        for sec_name, pos in active_positions.items():
            remaining_stocks = []
            exited_capital = 0
            n_initial = len(pos["initial_stocks"]) # Always 6 for the math to work
            
            for st in pos["stocks"]:
                px = _price_on(df, st["ticker"], dt)
                rsi = _calc_rsi_on(df, st["ticker"], dt)
                
                if px is None:
                    remaining_stocks.append(st)
                    continue

                if rsi is not None and rsi < STOCK_RSI_EXIT:
                    # Individual stock exit
                    ret = (px / st["entry_price"]) - 1
                    realized = (pos["capital_allocated"] / n_initial) * (1 + ret)
                    current_capital += realized
                else:
                    remaining_stocks.append(st)
            
            pos["stocks"] = remaining_stocks
            
            # Sector level exit
            sec_ticker = rs_engine.SECTOR_INDICES.get(sec_name)
            sec_rs = _calc_rs_on(df, sec_ticker, "^NSEI", dt)
            sec_rsi = _calc_rsi_on(df, sec_ticker, dt)
            
            if sec_rs is not None and sec_rs < 1.0:
                secs_to_exit.append(sec_name)
            elif sec_rsi is not None and sec_rsi < SECTOR_RSI_EXIT:
                secs_to_exit.append(sec_name)
            elif not pos["stocks"]:
                secs_to_exit.append(sec_name)

        for sn in secs_to_exit:
            pos = active_positions.pop(sn)
            n_initial = len(pos["initial_stocks"])
            for st in pos["stocks"]:
                px = _price_on(df, st["ticker"], dt)
                if px:
                    ret = (px / st["entry_price"]) - 1
                    realized = (pos["capital_allocated"] / n_initial) * (1 + ret)
                    current_capital += realized
                else:
                    current_capital += (pos["capital_allocated"] / n_initial)

        # B. Enter New Sectors
        if len(active_positions) < max_sectors:
            rankings = []
            for name, ticker in rs_engine.SECTOR_INDICES.items():
                if name not in rs_engine.SECTOR_STOCKS: continue
                rs = _calc_rs_on(df, ticker, "^NSEI", dt)
                if rs and rs > 1.01: # Slight threshold
                    rankings.append({"name": name, "rs": rs})
            
            rankings.sort(key=lambda x: x["rs"], reverse=True)
            
            for r in rankings:
                if len(active_positions) >= max_sectors: break
                if r["name"] in active_positions: continue
                
                # Pick 2L+2M+2S
                stocks = rs_engine.SECTOR_STOCKS.get(r["name"], [])
                by_cap = {"Large": [], "Mid": [], "Small": []}
                for t, cap in stocks:
                    s_rs = _calc_rs_on(df, t, "^NSEI", dt)
                    s_rsi = _calc_rsi_on(df, t, dt)
                    if s_rs and s_rsi and s_rsi >= 50:
                        px = _price_on(df, t, dt)
                        if px:
                            by_cap[cap].append({"ticker": t, "rs": s_rs, "entry_price": px})
                
                selected_stocks = []
                for c in ["Large", "Mid", "Small"]:
                    group = sorted(by_cap[c], key=lambda x: x["rs"], reverse=True)
                    selected_stocks.extend(group[:2])
                
                if len(selected_stocks) >= 4:
                    free_slots = max_sectors - len(active_positions)
                    alloc = current_capital / free_slots
                    current_capital -= alloc
                    active_positions[r["name"]] = {
                        "entry_date": dt.strftime("%Y-%m-%d"),
                        "stocks": selected_stocks,
                        "initial_stocks": selected_stocks, # To track original count
                        "capital_allocated": alloc
                    }

        # C. Portfolio Value
        val = current_capital
        for sn, pos in active_positions.items():
            n_initial = len(pos["initial_stocks"])
            for st in pos["stocks"]:
                px = _price_on(df, st["ticker"], dt)
                if px:
                    val += (pos["capital_allocated"] / n_initial) * (px / st["entry_price"])
                else:
                    val += (pos["capital_allocated"] / n_initial)
        
        portfolio_curve.append({"date": dt.strftime("%Y-%m-%d"), "value": val})

    return portfolio_curve

if __name__ == "__main__":
    start = date(2021, 1, 1)
    end = date(2024, 5, 8)
    cap = 100000
    
    # Pre-download
    working_sectors = [
        "Nifty Auto", "Nifty Bank", "Nifty IT", "Nifty Pharma", "Nifty FMCG",
        "Nifty Metal", "Nifty Realty", "Nifty Energy", "Nifty Infra",
        "Nifty PSU Bank", "Nifty Media", "Nifty Finance"
    ]
    tickers = ["^NSEI"]
    for s_name in working_sectors:
        tickers.append(rs_engine.SECTOR_INDICES[s_name])
        for t, _ in rs_engine.SECTOR_STOCKS[s_name]:
            tickers.append(t)
    tickers = list(set(tickers))
    
    print(f"Downloading {len(tickers)} tickers...")
    data_dict = {}
    for i in range(0, len(tickers), 25):
        batch = tickers[i:i+25]
        batch_data = yf.download(batch, start=start-timedelta(days=150), end=end+timedelta(days=5), progress=False)["Close"]
        if isinstance(batch_data, pd.Series):
            data_dict[batch[0]] = batch_data
        else:
            for col in batch_data.columns: data_dict[col] = batch_data[col]
            
    full_df = pd.DataFrame(data_dict).ffill()
    full_df.index = pd.to_datetime(full_df.index).tz_localize(None)
    
    curve1 = run_v4_backtest(full_df, start, end, cap, 1)
    curve3 = run_v4_backtest(full_df, start, end, cap, 3)
    
    nifty_start = _price_on(full_df, "^NSEI", pd.Timestamp(start))
    nifty_end = _price_on(full_df, "^NSEI", pd.Timestamp(end))
    nifty_ret = (nifty_end / nifty_start - 1) * 100
    
    print(f"\nRESULTS {start} to {end}:")
    print(f"Final Value (Max 1 Sector):  Rs. {curve1[-1]['value']:,.0f} ({(curve1[-1]['value']/cap-1)*100:+.1f}%)")
    print(f"Final Value (Max 3 Sectors): Rs. {curve3[-1]['value']:,.0f} ({(curve3[-1]['value']/cap-1)*100:+.1f}%)")
    print(f"Nifty Return: {nifty_ret:+.1f}%")
