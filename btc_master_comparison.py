import yfinance as yf
import pandas as pd
import numpy as np
import logic

def run_surgical_btc(st_period, st_mult, timeframe, strike):
    try:
        df = yf.download('BTC-USD', period='2y', interval=timeframe, progress=False)
        if df.empty: return 0, 0, 0
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        df = logic.calculate_supertrend(df, period=st_period, multiplier=st_mult)
        df = logic.calculate_adx(df)
        
        cols = list(df.columns)
        dir_col = next((c for c in cols if f"SUPERTd_{st_period}_{st_mult}" in c), None)
        
        pos = 0
        trades = []
        delta_map = {'ATM': 0.5, 'OTM3': 0.2, 'ITM3': 0.8}
        delta = delta_map.get(strike, 0.5)
        
        for i in range(1, len(df)):
            signal = df[dir_col].iloc[i]
            prev_sig = df[dir_col].iloc[i-1]
            adx = df['ADX_14'].iloc[i]
            price = df['close'].iloc[i]
            
            if prev_sig == -1 and signal == 1 and adx > 20:
                if pos != 0 and trades: trades[-1]['exit'] = price
                pos = 1
                trades.append({'type': 'BUY', 'entry': price, 'entry_time': df.index[i]})
            elif prev_sig == 1 and signal == -1 and adx > 20:
                if pos != 0 and trades: trades[-1]['exit'] = price
                pos = -1
                trades.append({'type': 'SELL', 'entry': price, 'entry_time': df.index[i]})
                
        total_pnl = 0
        win = 0
        valid_trades = [t for t in trades if 'exit' in t]
        for t in valid_trades:
            move = (t['exit'] - t['entry']) / t['entry']
            if t['type'] == 'SELL': move = -move
            # Lowered slippage for Daily (fewer trades)
            trade_pnl = (move * 15 * delta) - 0.002 
            total_pnl += trade_pnl
            if trade_pnl > 0: win += 1
                
        return round(total_pnl * 100, 2), len(valid_trades), (win/len(valid_trades)*100 if valid_trades else 0)
    except: return 0, 0, 0

print(">>> BTC SUPREME RESEARCH (1D Timeframe - 2 Years) <<<")
results = []
for st in [(10,1), (10,1.5), (10,2)]:
    for strike in ['ATM', 'OTM3', 'ITM3']:
        roi, count, winrate = run_surgical_btc(st[0], st[1], '1d', strike)
        results.append({"Setup": f"ST {st[0]}/{st[1]}", "Strike": strike, "Trades": count, "WinRate": f"{winrate:.1f}%", "ROI": f"{roi}%"})

df_res = pd.DataFrame(results).sort_values(by="ROI", key=lambda x: x.str.replace('%','').astype(float), ascending=False)
print(df_res.to_string(index=False))
