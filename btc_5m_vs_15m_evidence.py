import yfinance as yf
import pandas as pd
import numpy as np
import logic
import datetime

def backtest_engine(df, st_period, st_mult, strike_delta):
    df = logic.calculate_supertrend(df, period=st_period, multiplier=st_mult)
    dir_col = next((c for c in df.columns if f"SUPERTd_{st_period}_{st_mult}" in c), None)
    
    pos = 0
    trades = []
    
    for i in range(1, len(df)):
        signal = df[dir_col].iloc[i]
        prev_sig = df[dir_col].iloc[i-1]
        price = df['close'].iloc[i]
        
        if prev_sig == -1 and signal == 1:
            if pos != 0: trades[-1]['exit'] = price; trades[-1]['exit_time'] = df.index[i]
            pos = 1
            trades.append({'type': 'BUY', 'entry': price, 'entry_time': df.index[i]})
        elif prev_sig == 1 and signal == -1:
            if pos != 0: trades[-1]['exit'] = price; trades[-1]['exit_time'] = df.index[i]
            pos = -1
            trades.append({'type': 'SELL', 'entry': price, 'entry_time': df.index[i]})
            
    # ROI Calculation
    monthly_stats = {}
    for t in trades:
        if 'exit' in t:
            month = t['entry_time'].strftime('%Y-%m')
            move = (t['exit'] - t['entry']) / t['entry']
            if t['type'] == 'SELL': move = -move
            # Option ROI: 20x Leverage * Delta - 0.2% cost (Very tight)
            roi = (move * 20 * strike_delta) - 0.002
            monthly_stats[month] = monthly_stats.get(month, 0) + roi
            
    return monthly_stats

def get_full_report():
    print("Fetching 60 days of 5m and 15m data for BTC...")
    df5m = yf.download('BTC-USD', period='60d', interval='5m', progress=False)
    df15m = yf.download('BTC-USD', period='60d', interval='15m', progress=False)
    
    for d in [df5m, df15m]:
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
        d.columns = [str(c).lower().strip() for c in d.columns]

    strikes = {'ATM': 0.5, 'ITM3': 0.8, 'OTM3': 0.2}
    
    final_data = []
    for tf_name, df in [('5m', df5m), ('15m', df15m)]:
        for s_name, delta in strikes.items():
            stats = backtest_engine(df, 10, 1.5, delta)
            for month, roi in stats.items():
                final_data.append({
                    "Month": month,
                    "Timeframe": tf_name,
                    "Strike": s_name,
                    "Monthly ROI (%)": round(roi * 100, 2)
                })
                
    report = pd.DataFrame(final_data)
    # Pivot for comparison
    pivot = report.pivot_table(index=['Month', 'Strike'], columns='Timeframe', values='Monthly ROI (%)')
    print("\n>>> BTC EVIDENCE REPORT: 5M vs 15M (ST 10/1.5) <<<")
    print(pivot)
    pivot.to_csv("btc_evidence_pivot.csv")

if __name__ == "__main__":
    get_full_report()
