import time
import datetime
import yfinance as yf
import pandas as pd
import db
import logic
import executor
import delta_executor
import crypto_roller
import notifier

def log_master(msg):
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    full_msg = f"[{timestamp}] [MASTER] {msg}"
    print(full_msg)
    # Heartbeat/Alert if error
    if "Error" in msg or "ALERT" in msg:
        notifier.send_telegram_msg(msg)

def run_nifty_slot(slot_name, period, multiplier, timeframe):
    if db.get_param(f'nifty_{slot_name}_status', 'OFF') == 'OFF': return
    try:
        symbol = "^NSEI"
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
            executor.place_order("BUY", spot_price)
        elif prev_signal == 1 and last_signal == -1:
            executor.place_order("SELL", spot_price)
        executor.check_and_roll_nifty()
    except Exception as e: log_master(f"Nifty Error: {e}")

def run_crypto_master():
    """CRYPTO 5M SURGICAL ENGINE"""
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF': return
    
    asset = db.get_param('crypto_asset', 'BTC')
    # USER REQUEST: FORCE 5 MINUTE TIMEFRAME
    timeframe = "5m" 
    
    try:
        symbol = f"{asset}-USD"
        df = yf.download(symbol, period="1d", interval=timeframe, progress=False)
        if df.empty: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]
        
        # Supertrend 10/1.5 (Dr. Saab's Favourite)
        df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
        df = logic.calculate_adx(df)
        
        last_st = df['SUPERTd_10_1.5'].iloc[-1]
        prev_st = df['SUPERTd_10_1.5'].iloc[-2]
        last_adx = df['ADX_14'].iloc[-1]
        
        # SYNC CHECK (Handles Re-connections)
        delta_executor.sync_delta_position()
        active_symbol = db.get_param("crypto_active_symbol", "")
        
        # MISMATCH CORRECTION: If Signal flipped while app was offline
        if last_adx > 15: # Aggressive threshold
            has_bullish = ("-C-" in active_symbol) or ("CALL" in active_symbol.upper())
            has_bearish = ("-P-" in active_symbol) or ("PUT" in active_symbol.upper())
            has_nothing = not active_symbol or "PAPER" in active_symbol
            
            if last_st == 1 and (has_nothing or has_bearish):
                log_master(f"5M ALERT: Signal is BUY. Flipping position...")
                delta_executor.execute_crypto_trade(asset, "BUY")
            elif last_st == -1 and (has_nothing or has_bullish):
                log_master(f"5M ALERT: Signal is SELL. Flipping position...")
                delta_executor.execute_crypto_trade(asset, "SELL")

        # CONTINUOUS ROLLING CHECK
        crypto_roller.check_and_roll_crypto()
        
    except Exception as e:
        log_master(f"Crypto Connection Error: {e}")
        # ALARM logic can be added here (e.g. notify user)

def main():
    log_master("🔥 BHARAT ALGOVERSE: 5M MOBILE ENGINE STARTING...")
    while True:
        # Check Nifty (15m)
        run_nifty_slot("agg", 10, 1, "15m")
        run_nifty_slot("sur", 10, 2, "15m")
        # Check Crypto (5m)
        run_crypto_master()
        time.sleep(30)

if __name__ == "__main__":
    main()
