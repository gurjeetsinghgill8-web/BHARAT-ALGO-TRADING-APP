
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import invest_rs_engine as rs_engine
import os
import json

def _price_on_fast(data_dict, ticker, dt):
    try:
        df = data_dict.get(ticker)
        if df is None: return None
        target = pd.Timestamp(dt)
        if target in df.index: return float(df.loc[target, 'Close'])
        # Pad search
        idx = df.index.get_indexer([target], method='pad')[0]
        if idx == -1: return None
        return float(df['Close'].iloc[idx])
    except: return None

def calculate_supertrend(df, period=15, multiplier=1.5):
    try:
        high = df['High'].values
        low = df['Low'].values
        close = df['Close'].values
        hl = high - low
        hc = np.abs(high - np.roll(close, 1)); hc[0] = hl[0]
        lc = np.abs(low - np.roll(close, 1)); lc[0] = hl[0]
        tr = np.maximum(hl, np.maximum(hc, lc))
        alpha = 1 / period
        atr = np.zeros(len(df))
        atr[period-1] = np.mean(tr[:period])
        for i in range(period, len(df)): atr[i] = (tr[i] - atr[i-1]) * alpha + atr[i-1]
        hl2 = (high + low) / 2
        upper, lower = hl2 + (multiplier * atr), hl2 - (multiplier * atr)
        f_up, f_lo = np.zeros(len(df)), np.zeros(len(df))
        st_val, st_dir = np.zeros(len(df)), np.ones(len(df))
        for i in range(1, len(df)):
            f_up[i] = upper[i] if upper[i] < f_up[i-1] or close[i-1] > f_up[i-1] else f_up[i-1]
            f_lo[i] = lower[i] if lower[i] > f_lo[i-1] or close[i-1] < f_lo[i-1] else f_lo[i-1]
            if st_dir[i-1] == 1:
                st_dir[i] = 1 if close[i] > f_lo[i] else -1
                st_val[i] = f_lo[i] if st_dir[i] == 1 else f_up[i]
            else:
                st_dir[i] = -1 if close[i] < f_up[i] else 1
                st_val[i] = f_up[i] if st_dir[i] == -1 else f_lo[i]
        res = pd.DataFrame(index=df.index); res['Close'] = close; res['st_dir'] = st_dir
        return res
    except: return None

def run_deep_study_fast(data_dict, st_data, start_date, end_date, capital, max_stocks, strategy_type):
    current_capital = float(capital); active_positions = {}
    step_dates = pd.date_range(start_date, end_date, freq='D')
    all_tickers = [t for t in st_data.keys() if t != "^NSEI"]
    
    for i, dt in enumerate(step_dates):
        exited = []
        for t, pos in active_positions.items():
            df_st = st_data.get(t)
            if df_st is None: continue
            
            # Safe ST lookup
            idx = df_st.index.get_indexer([dt], method='pad')[0]
            if idx != -1:
                row = df_st.iloc[idx]
                if row['st_dir'] == -1:
                    current_capital += pos['cap_alloc'] * (row['Close'] / pos['entry_price'])
                    exited.append(t)
        
        for t in exited: active_positions.pop(t)
        
        if i % 7 == 0 and len(active_positions) < max_stocks:
            cands = []
            for t in all_tickers:
                if t in active_positions: continue
                p_now, p_old = _price_on_fast(data_dict, t, dt), _price_on_fast(data_dict, t, dt - timedelta(days=55))
                n_now, n_old = _price_on_fast(data_dict, "^NSEI", dt), _price_on_fast(data_dict, "^NSEI", dt - timedelta(days=55))
                
                if all([p_now, p_old, n_now, n_old]):
                    rs = (p_now / p_old) / (n_now / n_old)
                    # Broadened RS thresholds: Emerging (1.02-1.07), Running (> 1.07)
                    if (strategy_type == "EMERGING" and 1.01 < rs < 1.07) or (strategy_type == "RUNNING" and rs >= 1.07):
                        df_st = st_data.get(t)
                        if df_st is not None:
                            st_idx = df_st.index.get_indexer([dt], method='pad')[0]
                            if st_idx != -1 and df_st.iloc[st_idx]['st_dir'] == 1:
                                cands.append({"t": t, "rs": rs, "p": p_now})
            
            cands.sort(key=lambda x: x["rs"], reverse=True)
            for c in cands[:(max_stocks - len(active_positions))]:
                if current_capital <= 0: break
                alloc = current_capital / (max_stocks - len(active_positions))
                current_capital -= alloc
                active_positions[c["t"]] = {"entry_price": c["p"], "cap_alloc": alloc}
    val = current_capital
    for t, pos in active_positions.items():
        px = _price_on_fast(data_dict, t, end_date); val += pos['cap_alloc'] * (px / pos['entry_price']) if px else pos['cap_alloc']
    return val

if __name__ == "__main__":
    start_time = datetime.now()
    all_t = list(set(["^NSEI"] + [t for s in rs_engine.SECTOR_STOCKS.values() for t, _ in s]))
    print(f"Downloading {len(all_t)} stocks...")
    raw = yf.download(all_t, start="2020-01-01", end="2024-05-10", progress=True)
    full_dict = {}
    for t in (raw.columns.get_level_values(1).unique() if isinstance(raw.columns, pd.MultiIndex) else [raw.name]):
        if not t: continue
        try:
            d = pd.DataFrame({c: raw[c][t] for c in ["Open", "High", "Low", "Close"] if c in raw and t in raw[c]}).dropna()
            if not d.empty: full_dict[t] = d
        except: continue
    print(f"Pre-processed {len(full_dict)} tickers.")
    final_results = []
    for p, m in [(15, 1.5), (15, 1.0), (15, 2.0)]:
        print(f"\n>>> ST({p}, {m})")
        st_data = {t: calculate_supertrend(df, p, m) for t, df in full_dict.items()}
        st_data = {t: v for t, v in st_data.items() if v is not None}
        for strat in ["EMERGING", "RUNNING"]:
            for year in [2021, 2022, 2023, 2024]:
                y_s, y_e = date(year, 1, 1), (date(year, 12, 31) if year < 2024 else date(2024, 5, 8))
                n_s, n_e = _price_on_fast(full_dict, "^NSEI", y_s), _price_on_fast(full_dict, "^NSEI", y_e)
                nifty_ret = (n_e / n_s - 1) * 100 if n_s and n_e else 0
                val = run_deep_study_fast(full_dict, st_data, y_s, y_e, 100000, 5, strat)
                ret = (val / 100000 - 1) * 100
                final_results.append({"year": year, "strat": strat, "st_p": p, "st_m": m, "nifty": round(nifty_ret, 2), "return": round(ret, 2)})
                print(f"  {strat} {year}: {ret:+.1f}% (Nifty: {nifty_ret:+.1f}%)")
    with open("deep_study_results.json", "w") as f: json.dump(final_results, f, indent=4)
    print(f"\nDone in {(datetime.now() - start_time).seconds}s")
