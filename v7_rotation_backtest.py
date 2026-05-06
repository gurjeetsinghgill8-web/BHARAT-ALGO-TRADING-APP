
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import os
import json

# ============================================================
# 1. UNIVERSE DEFINITION
# ============================================================
UNIVERSE = {
    'Large': ['M&M.NS', 'MARUTI.NS', 'BAJAJ-AUTO.NS', 'EICHERMOT.NS', 'HEROMOTOCO.NS', 'HDFCBANK.NS', 'ICICIBANK.NS', 'KOTAKBANK.NS', 'AXISBANK.NS', 'INDUSINDBK.NS', 'TCS.NS', 'INFY.NS', 'HCLTECH.NS', 'WIPRO.NS', 'TECHM.NS', 'SUNPHARMA.NS', 'DRREDDY.NS', 'CIPLA.NS', 'DIVISLAB.NS', 'HINDUNILVR.NS', 'ITC.NS', 'NESTLEIND.NS', 'BRITANNIA.NS', 'DABUR.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS', 'HINDALCO.NS', 'VEDL.NS', 'SAIL.NS', 'DLF.NS', 'GODREJPROP.NS', 'RELIANCE.NS', 'ONGC.NS', 'NTPC.NS', 'POWERGRID.NS', 'ADANIGREEN.NS', 'SBIN.NS', 'BANKBARODA.NS', 'CANBK.NS', 'PNB.NS', 'LT.NS', 'ADANIPORTS.NS', 'IRFC.NS', 'BAJFINANCE.NS', 'BAJAJFINSV.NS', 'HDFCAMC.NS', 'LICHSGFIN.NS', 'HAL.NS', 'BEL.NS'],
    'Mid': ['BOSCHLTD.NS', 'MOTHERSON.NS', 'BALKRISIND.NS', 'FEDERALBNK.NS', 'BANDHANBNK.NS', 'IDFCFIRSTB.NS', 'MPHASIS.NS', 'PERSISTENT.NS', 'AUROPHARMA.NS', 'ALKEM.NS', 'IPCALAB.NS', 'MARICO.NS', 'GODREJCP.NS', 'NATIONALUM.NS', 'RATNAMANI.NS', 'PRESTIGE.NS', 'OBEROIRLTY.NS', 'PHOENIXLTD.NS', 'BRIGADE.NS', 'CESC.NS', 'TORNTPOWER.NS', 'UNIONBANK.NS', 'INDIANB.NS', 'RVNL.NS', 'IRCON.NS', 'NBCC.NS', 'KEC.NS', 'MUTHOOTFIN.NS', 'CHOLAFIN.NS', 'M&MFIN.NS', 'ZEEL.NS', 'SUNTV.NS', 'NETWORK18.NS', 'CAMS.NS', 'ANGELONE.NS', 'POLICYBZR.NS', 'PAYTM.NS', 'NYKAA.NS', 'BEML.NS', 'COCHINSHIP.NS', 'MAZDOCK.NS'],
    'Small': ['NATCOPHARM.NS', 'SUNTECK.NS', 'KPIL.NS', 'PVRINOX.NS', 'MTAR.NS', 'PARAS.NS', 'CAMS.NS', 'ANGELONE.NS', 'NBCC.NS', 'RVNL.NS']
}

# ============================================================
# 2. INDICATOR HELPERS
# ============================================================
def calculate_supertrend(df, period=10, multiplier=1.5):
    df = df.copy()
    high = df['High']
    low = df['Low']
    close = df['Close']
    
    hl = high - low
    hc = (high - close.shift(1)).abs()
    lc = (low - close.shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    hl2 = (high + low) / 2
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)

    final_upper = np.zeros(len(df))
    final_lower = np.zeros(len(df))
    st_dir = np.ones(len(df))
    
    basic_upper = basic_upper.fillna(0).values
    basic_lower = basic_lower.fillna(0).values
    close_vals = close.values
    
    for i in range(len(df)):
        if i == 0:
            final_upper[i] = basic_upper[i]
            final_lower[i] = basic_lower[i]
            st_dir[i] = -1
            continue
            
        if basic_upper[i] < final_upper[i-1] or close_vals[i-1] > final_upper[i-1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i-1]
            
        if basic_lower[i] > final_lower[i-1] or close_vals[i-1] < final_lower[i-1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i-1]
            
        if st_dir[i-1] == 1:
            st_dir[i] = 1 if close_vals[i] > final_lower[i] else -1
        else:
            st_dir[i] = -1 if close_vals[i] < final_upper[i] else 1

    return st_dir

def calculate_factors(df, benchmark_df):
    if len(df) < 90: return None, None, None
    rets = df['Close'].pct_change().dropna().tail(90)
    vol = rets.std()
    l_score = 1.0 / vol if vol != 0 else 0
    m_score = (df['Close'].iloc[-1] / df['Close'].iloc[-90]) - 1
    stock_perf = df['Close'].iloc[-1] / df['Close'].iloc[-55]
    nifty_perf = benchmark_df['Close'].iloc[-1] / benchmark_df['Close'].iloc[-55]
    s_score = stock_perf / nifty_perf
    return l_score, m_score, s_score

# ============================================================
# 3. BACKTEST ENGINE
# ============================================================
def run_rotation_backtest(all_data, universe_name, st_period=10, st_mult=1.5, start_date='2021-01-01', end_date='2024-05-01'):
    tickers = UNIVERSE[universe_name]
    bench_ticker = "^NSEI"
    if bench_ticker not in all_data: return pd.DataFrame()
    
    dates = all_data[bench_ticker].index
    dates = dates[(dates >= start_date) & (dates <= end_date)]
    
    capital = 100000.0
    portfolio = {} 
    portfolio_value = []
    max_stocks = 5
    
    for i, dt in enumerate(dates):
        if i < 100: continue
        
        current_val = capital
        for t, pos in portfolio.items():
            if t in all_data and dt in all_data[t].index:
                px = all_data[t]['Close'].loc[dt]
                if not np.isnan(px):
                    current_val += pos['shares'] * px
                    pos['last_px'] = px
                else:
                    current_val += pos['shares'] * pos.get('last_px', pos['entry_price'])
            else:
                current_val += pos['shares'] * pos.get('last_px', pos['entry_price'])
        
        portfolio_value.append({'Date': dt, 'Value': current_val})
        
        for t in list(portfolio.keys()):
            if t in all_data and dt in all_data[t].index:
                st_dir = all_data[t]['ST_DIR'].loc[dt]
                if st_dir == -1: 
                    px = all_data[t]['Close'].loc[dt]
                    capital += portfolio[t]['shares'] * px
                    del portfolio[t]

        if len(portfolio) < max_stocks:
            # Regime Filter: Only enter if Nifty is Bullish (ST 10/1.5)
            # Actually, let's calculate Nifty's Supertrend and use it.
            # We already have ST_DIR in all_data, but for Nifty we might need a fixed one.
            nifty_st = all_data[bench_ticker]['ST_DIR_10_1.5'].loc[dt] if 'ST_DIR_10_1.5' in all_data[bench_ticker].columns else 1
            
            if nifty_st == 1:
                candidates = []
                for t in tickers:
                    if t in portfolio or t not in all_data or dt not in all_data[t].index: continue
                    st_dir = all_data[t]['ST_DIR'].loc[dt]
                    if st_dir == 1:
                        idx = all_data[t].index.get_loc(dt)
                        if idx < 90: continue
                        df_sub = all_data[t].iloc[idx-90:idx+1]
                        bench_sub = all_data[bench_ticker].iloc[idx-90:idx+1]
                        l, m, s = calculate_factors(df_sub, bench_sub)
                        if l is not None:
                            candidates.append({'ticker': t, 'l': l, 'm': m, 's': s})

            
            if candidates:
                df_cand = pd.DataFrame(candidates)
                df_cand['r_l'] = df_cand['l'].rank(ascending=False)
                df_cand['r_m'] = df_cand['m'].rank(ascending=False)
                df_cand['r_s'] = df_cand['s'].rank(ascending=False)
                df_cand['score'] = (2*df_cand['r_l'] + 2*df_cand['r_m'] + 2*df_cand['r_s'])
                df_cand = df_cand.sort_values('score')
                
                slots = max_stocks - len(portfolio)
                to_buy = df_cand.head(slots)
                if not to_buy.empty:
                    alloc_per_stock = capital / slots
                    for _, row in to_buy.iterrows():
                        t = row['ticker']
                        try:
                            px = float(all_data[t]['Close'].loc[dt])
                        except KeyError:
                            continue
                        
                        if not np.isnan(px) and px > 0:
                            shares = alloc_per_stock / px
                            capital -= alloc_per_stock
                            portfolio[t] = {'shares': shares, 'entry_price': px, 'last_px': px}

    return pd.DataFrame(portfolio_value)

# ============================================================
# 4. MAIN EXECUTION
# ============================================================
if __name__ == "__main__":
    start_dt = "2021-01-01"
    end_dt = datetime.now().strftime("%Y-%m-%d")
    
    all_tickers = sorted(list(set(UNIVERSE['Large'] + UNIVERSE['Mid'] + UNIVERSE['Small'] + ["^NSEI"])))
    print(f"Downloading data for {len(all_tickers)} tickers...")
    
    all_data = {}
    for t in all_tickers:
        try:
            df = yf.download(t, start="2020-01-01", end=end_dt, interval="1d", progress=False)
            if df.empty: continue
            
            # Flatten MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            if len(df) < 150: continue
            df = df.ffill().dropna()
            
            df['ST_DIR_10_1'] = calculate_supertrend(df, 10, 1.0)
            df['ST_DIR_10_1.5'] = calculate_supertrend(df, 10, 1.5)
            df['ST_DIR_10_2'] = calculate_supertrend(df, 10, 2.0)
            all_data[t] = df
            print(f"Loaded {t}")
        except Exception as e:
            print(f"Error {t}: {e}")

    results = []
    variants = [(10, 1.0, 'ST_DIR_10_1'), (10, 1.5, 'ST_DIR_10_1.5'), (10, 2.0, 'ST_DIR_10_2')]
    caps = ['Large', 'Mid', 'Small']
    
    for cap in caps:
        for period, mult, col in variants:
            print(f"Backtest: {cap} | ST {period}/{mult}")
            for t in all_data:
                if col in all_data[t].columns:
                    all_data[t]['ST_DIR'] = all_data[t][col]
            curve = run_rotation_backtest(all_data, cap, period, mult, start_dt, end_dt)
            if not curve.empty:
                curve['Cap'] = cap
                curve['Variant'] = f"{period}/{mult}"
                results.append(curve)

    if not results:
        print("No results generated. Check data availability.")
    else:
        full_res = pd.concat(results)
        full_res['Date'] = pd.to_datetime(full_res['Date'])
        full_res['Year'] = full_res['Date'].dt.year
        
        print("\nYEAR-ON-YEAR PERFORMANCE (%)")
        yoy_summary = []
        
        # Group by Cap and Variant to print individual stats
        for (cap, variant), group in full_res.groupby(['Cap', 'Variant']):
            group = group.sort_values('Date')
            years = sorted(group['Year'].unique())
            rets = []
            for yr in years:
                sub = group[group['Year'] == yr]
                y_start = sub['Value'].iloc[0]
                y_end = sub['Value'].iloc[-1]
                ret = (y_end / y_start - 1) * 100
                rets.append(f"{yr}: {ret:.1f}%")
            
            total_ret = (group['Value'].iloc[-1] / 100000.0 - 1) * 100
            print(f"[{cap} | ST {variant}] Total: {total_ret:.1f}% | " + " | ".join(rets))
            yoy_summary.append({'Cap': cap, 'Variant': variant, 'Total': f"{total_ret:.1f}%", 'YOY': " | ".join(rets)})

        # Nifty Comparison
        if '^NSEI' in all_data:
            nifty = all_data['^NSEI']['Close']
            nifty_yoy = nifty.resample('YE').last().pct_change() * 100
            nifty_dict = {str(k.year): f"{v:.1f}%" for k, v in nifty_yoy.dropna().to_dict().items()}
        else:
            nifty_dict = {}

        with open('rotation_backtest_report.json', 'w') as f:
            json.dump({'summary': yoy_summary, 'nifty': nifty_dict}, f, indent=4)
