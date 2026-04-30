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
    # Check if this slot is ON
    if db.get_param(f'nifty_{slot_name}_status', 'OFF') == 'OFF':
        return

    symbol = "^NSEI"
    try:
        df = yf.download(symbol, period="1d", interval=timeframe, progress=False)
        if df.empty: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]

        df = logic.calculate_supertrend(df, period=period, multiplier=multiplier)
        dir_col = f"SUPERTd_{period}_{multiplier}"
        last_signal = df[dir_col].iloc[-1]
        prev_signal = df[dir_col].iloc[-2]
        spot_price = df['close'].iloc[-1]

        # Get current position for THIS slot
        active_key = db.get_param(f"nifty_{slot_name}_active_key", "")

        # Signal Logic
        if prev_signal == -1 and last_signal == 1:
            log_master(f"Nifty {slot_name.upper()} BUY Signal!")
            executor.place_order("BUY", spot_price) # This needs slot awareness
        elif prev_signal == 1 and last_signal == -1:
            log_master(f"Nifty {slot_name.upper()} SELL Signal!")
            executor.place_order("SELL", spot_price)
            
        # Rolling Profit Check
        executor.check_and_roll_nifty() # Currently global, but fine for now
    except Exception as e:
        log_master(f"Nifty Slot {slot_name} Error: {e}")

def run_crypto_master():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF':
        return
    
    asset = db.get_param('crypto_asset', 'BTC')
    timeframe = db.get_param('crypto_timeframe', '1h')
    
    try:
        # Fetch Data
        symbol = f"{asset}-USD"
        df = yf.download(symbol, period="1d", interval=timeframe, progress=False)
        if df.empty: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]

        # Strategy: Supertrend (10, 1.5) + ADX > 20
        df = logic.calculate_supertrend(df, period=14, multiplier=1.5)
        df = logic.calculate_adx(df)
        
        last_st = df['SUPERTd_14_1.5'].iloc[-1]
        prev_st = df['SUPERTd_14_1.5'].iloc[-2]
        last_adx = df['ADX_14'].iloc[-1]
        
        # Signal
        if prev_st == -1 and last_st == 1 and last_adx > 20:
            log_master("CRYPTO BUY Signal!")
            delta_executor.execute_crypto_trade(asset, "BUY")
        elif prev_st == 1 and last_st == -1 and last_adx > 20:
            log_master("CRYPTO SELL Signal!")
            delta_executor.execute_crypto_trade(asset, "SELL")
            
        # Rolling Profit Check
        crypto_roller.check_and_roll_crypto()
    except Exception as e:
        log_master(f"Crypto Master Error: {e}")

def main():
    log_master("BHARAT ALGOVERSE 2.0 - SUPREME ENGINE STARTED")
    log_master("Running Dual Nifty (Aggressive + Surgical) + Crypto Rolling")
    
    while True:
        # 1. Nifty Aggressive (10/1)
        run_nifty_slot("agg", 10, 1, "15m")
        
        # 2. Nifty Surgical (10/2)
        run_nifty_slot("sur", 10, 2, "15m")
        
        # 3. Crypto Master
        run_crypto_master()
        
        time.sleep(30) # Tick every 30s

if __name__ == "__main__":
    main()

# SUPREME CLOUD SYNC: 2026-04-30
