
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import invest_rs_engine as rs_engine

# ── Config V5.0 "PURE STOCK ALPHA" ──────────────────────────────
RS_PERIOD         = 55      
STOCK_RSI_EXIT    = 50      
STEP_DAYS         = 7       
MAX_STOCKS        = 10      # Pick top 10 stocks across all sectors

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

def run_v5_stock_backtest(df, start_date: date, end_date: date, capital: float):
    current_capital = float(capital)
    active_stocks = {} # ticker -> {entry_price, entry_date, capital_allocated}
    portfolio_curve = []
    
    step_dates = []
    curr = start_date
    while curr <= end_date:
        step_dates.append(pd.Timestamp(curr))
        curr += timedelta(days=STEP_DAYS)

    all_tickers = []
    for s_list in rs_engine.SECTOR_STOCKS.values():
        all_tickers += [t for t, _ in s_list]
    all_tickers = list(set(all_tickers))

    for dt in step_dates:
        # A. Exit weak stocks
        tickers_to_exit = []
        for t, pos in active_stocks.items():
            px = _price_on(df, t, dt)
            rsi = _calc_rsi_on(df, t, dt)
            rs = _calc_rs_on(df, t, "^NSEI", dt)
            
            # Exit if RSI < 50 OR RS < 1.0 (relative weakness)
            if rsi is not None and rsi < STOCK_RSI_EXIT:
                tickers_to_exit.append(t)
            elif rs is not None and rs < 1.0:
                tickers_to_exit.append(t)
        
        for t in tickers_to_exit:
            pos = active_stocks.pop(t)
            px = _price_on(df, t, dt)
            if px:
                ret = (px / pos["entry_price"]) - 1
                current_capital += pos["capital_allocated"] * (1 + ret)
            else:
                current_capital += pos["capital_allocated"]

        # B. Enter new momentum stocks
        if len(active_stocks) < MAX_STOCKS:
            candidates = []
            for t in all_tickers:
                if t in active_stocks: continue
                rs = _calc_rs_on(df, t, "^NSEI", dt)
                rsi = _calc_rsi_on(df, t, dt)
                if rs and rs > 1.05 and rsi and rsi >= 50: # Strong momentum only
                    px = _price_on(df, t, dt)
                    if px:
                        candidates.append({"ticker": t, "rs": rs, "price": px})
            
            candidates.sort(key=lambda x: x["rs"], reverse=True)
            
            free_slots = MAX_STOCKS - len(active_stocks)
            for cand in candidates[:free_slots]:
                alloc = current_capital / (MAX_STOCKS - len(active_stocks))
                current_capital -= alloc
                active_stocks[cand["ticker"]] = {
                    "entry_price": cand["price"],
                    "entry_date": dt.strftime("%Y-%m-%d"),
                    "capital_allocated": alloc
                }

        # C. Value
        val = current_capital
        for t, pos in active_stocks.items():
            px = _price_on(df, t, dt)
            if px:
                val += pos["capital_allocated"] * (px / pos["entry_price"])
            else:
                val += pos["capital_allocated"]
        
        portfolio_curve.append({"date": dt.strftime("%Y-%m-%d"), "value": val})

    return portfolio_curve

if __name__ == "__main__":
    start = date(2021, 1, 1)
    end = date(2024, 5, 8)
    cap = 100000
    
    # Download
    all_tickers = ["^NSEI"]
    for s_list in rs_engine.SECTOR_STOCKS.values():
        all_tickers += [t for t, _ in s_list]
    all_tickers = list(set(all_tickers))
    
    print(f"Downloading {len(all_tickers)} stocks...")
    data_dict = {}
    for i in range(0, len(all_tickers), 25):
        batch = all_tickers[i:i+25]
        batch_data = yf.download(batch, start=start-timedelta(days=150), end=end+timedelta(days=5), progress=False)["Close"]
        if isinstance(batch_data, pd.Series):
            data_dict[batch[0]] = batch_data
        else:
            for col in batch_data.columns: data_dict[col] = batch_data[col]
            
    full_df = pd.DataFrame(data_dict).ffill()
    full_df.index = pd.to_datetime(full_df.index).tz_localize(None)
    
    curve = run_v5_stock_backtest(full_df, start, end, cap)
    
    nifty_start = _price_on(full_df, "^NSEI", pd.Timestamp(start))
    nifty_end = _price_on(full_df, "^NSEI", pd.Timestamp(end))
    nifty_ret = (nifty_end / nifty_start - 1) * 100
    
    print(f"\nRESULTS {start} to {end}:")
    print(f"Final Value (Pure Stock Momentum): Rs. {curve[-1]['value']:,.0f} ({(curve[-1]['value']/cap-1)*100:+.1f}%)")
    print(f"Nifty Return: {nifty_ret:+.1f}%")
