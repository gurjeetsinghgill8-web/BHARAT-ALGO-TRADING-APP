import pandas as pd
import yfinance as yf
import logic
import warnings
warnings.filterwarnings('ignore')

def test_adx_threshold(threshold, days=365):
    print(f"\n--- Testing ADX > {threshold} ---")
    df = yf.download("BTC-USD", period=f"{days}d", interval="1h", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    
    # Calculate indicators
    df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
    st_val_col = "SUPERT_10_1.5"
    dir_col = "SUPERTd_10_1.5"
    
    df['adx'] = logic.calculate_adx(df, 14)
    df['prev_dir'] = df[dir_col].shift(1)
    
    trades = []
    current_pos = None
    entry_spot = 0.0
    
    for idx, row in df.dropna(subset=[dir_col, 'prev_dir']).iterrows():
        prev_dir = row['prev_dir']
        last_dir = row[dir_col]
        adx_val = row['adx'] if not pd.isna(row['adx']) else 0
        
        signal = None
        if prev_dir == -1 and last_dir == 1 and adx_val >= threshold:
            signal = "BUY CE"
        elif prev_dir == 1 and last_dir == -1 and adx_val >= threshold:
            signal = "BUY PE"
            
        if signal and signal != current_pos:
            if current_pos:
                spot_move = row['close'] - entry_spot
                realized = spot_move * 0.55 if "CE" in current_pos else -spot_move * 0.55
                if realized < -500: realized = -500
                net_pnl = realized - 4.0
                trades.append(net_pnl)
                
            current_pos = signal
            entry_spot = row['close']
            
    if trades:
        wins = len([t for t in trades if t > 0])
        total = len(trades)
        win_rate = (wins / total) * 100
        total_pnl = sum(trades)
        
        # Max Drawdown
        cum_pnl = pd.Series(trades).cumsum()
        peak = cum_pnl.expanding(min_periods=1).max()
        dd = (cum_pnl - peak) / 5000 * 100  # assuming 5k capital
        max_dd = dd.min()
        
        print(f"Total Trades : {total}")
        print(f"Win Rate     : {win_rate:.1f}%")
        print(f"Total P&L    : ${total_pnl:.2f}")
        print(f"Max Drawdown : {max_dd:.1f}%")
        
test_adx_threshold(20)
test_adx_threshold(25)

# SUPREME CLOUD SYNC: 2026-04-30
