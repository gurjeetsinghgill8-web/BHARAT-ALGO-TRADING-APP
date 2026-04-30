import time
import datetime
import yfinance as yf
import pandas as pd
import db
import logic
import executor
import delta_executor
import crypto_roller

def log_master(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [MASTER] {msg}")

def run_nifty_slot(slot_name, period, multiplier, timeframe):
    """Processes a single Nifty strategy slot."""
    if db.get_param(f'nifty_{slot_name}_status', 'OFF') == 'OFF': return

    symbol = "^NSEI"
    try:
        df = yf.download(symbol, period="2d", interval=timeframe, progress=False)
        if df.empty: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]

        df = logic.calculate_supertrend(df, period=period, multiplier=multiplier)
        dir_col = f"SUPERTd_{period}_{multiplier}"
        last_signal = df[dir_col].iloc[-1]
        prev_signal = df[dir_col].iloc[-2]
        spot_price = df['close'].iloc[-1]

        if prev_signal == -1 and last_signal == 1:
            log_master(f"Nifty {slot_name.upper()} BUY Signal!")
            executor.place_order("BUY", spot_price)
        elif prev_signal == 1 and last_signal == -1:
            log_master(f"Nifty {slot_name.upper()} SELL Signal!")
            executor.place_order("SELL", spot_price)
            
        executor.check_and_roll_nifty()
    except Exception as e:
        log_master(f"Nifty Slot {slot_name} Error: {e}")

def run_crypto_master():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF': return
    
    asset = db.get_param('crypto_asset', 'BTC')
    timeframe = db.get_param('crypto_timeframe', '1h')
    
    try:
        symbol = f"{asset}-USD"
        df = yf.download(symbol, period="2d", interval=timeframe, progress=False)
        if df.empty: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]

        # FIX: Using Period 10 and Multiplier 1.5 for Crypto as requested
        df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
        df = logic.calculate_adx(df)
        
        last_st = df['SUPERTd_10_1.5'].iloc[-1]
        prev_st = df['SUPERTd_10_1.5'].iloc[-2]
        last_adx = df['ADX_14'].iloc[-1]
        
        # Signal Crossover Logic
        if prev_st == -1 and last_st == 1:
            if last_adx > 20:
                log_master("CRYPTO BUY Signal (ADX Filter Passed)!")
                delta_executor.execute_crypto_trade(asset, "BUY")
            else:
                log_master(f"CRYPTO BUY Signal IGNORED (ADX: {last_adx:.1f} < 20)")
        elif prev_st == 1 and last_st == -1:
            if last_adx > 20:
                log_master("CRYPTO SELL Signal (ADX Filter Passed)!")
                delta_executor.execute_crypto_trade(asset, "SELL")
            else:
                log_master(f"CRYPTO SELL Signal IGNORED (ADX: {last_adx:.1f} < 20)")
            
        crypto_roller.check_and_roll_crypto()
    except Exception as e:
        log_master(f"Crypto Master Error: {e}")

def main():
    log_master("MASTER ENGINE RUNNING...")
    while True:
        run_nifty_slot("agg", 10, 1, "15m")
        run_nifty_slot("sur", 10, 2, "15m")
        run_crypto_master()
        time.sleep(30)

if __name__ == "__main__":
    main()
