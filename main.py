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
import os

def clear_terminal():
    # Clears terminal for a clean dashboard look
    os.system('cls' if os.name == 'nt' else 'clear')

def log_terminal(msg, type="INFO"):
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    color = ""
    if type == "TRADE": color = "🟢 "
    if type == "ALERT": color = "🚨 "
    if type == "ERROR": color = "❌ "
    
    full_msg = f"[{timestamp}] {color}{msg}"
    print(full_msg)
    
    # Send to Telegram for mobile alerts
    if type in ["TRADE", "ALERT", "ERROR"]:
        notifier.send_telegram_msg(full_msg)

def run_nifty_slot(slot_name, period, multiplier, timeframe):
    status = db.get_param(f'nifty_{slot_name}_status', 'OFF')
    if status == 'OFF': return
    
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
        
        signal_str = "BUY" if last_signal == 1 else "SELL"
        # log_terminal(f"NIFTY {slot_name.upper()} | Price: {spot_price:.2f} | Signal: {signal_str}")

        if prev_signal == -1 and last_signal == 1:
            log_terminal(f"NIFTY {slot_name.upper()} CROSSOVER: BUY @ {spot_price}", "TRADE")
            executor.place_order("BUY", spot_price)
        elif prev_signal == 1 and last_signal == -1:
            log_terminal(f"NIFTY {slot_name.upper()} CROSSOVER: SELL @ {spot_price}", "TRADE")
            executor.place_order("SELL", spot_price)
            
        executor.check_and_roll_nifty()
    except Exception as e:
        log_terminal(f"Nifty Error: {e}", "ERROR")

def run_crypto_master():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF': return
    
    asset = db.get_param('crypto_asset', 'BTC')
    timeframe = "5m" # Force 5m as requested by Dr. Saab
    
    try:
        symbol = f"{asset}-USD"
        df = yf.download(symbol, period="1d", interval=timeframe, progress=False)
        if df.empty: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower() for c in df.columns]
        
        df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
        df = logic.calculate_adx(df)
        
        last_st = df['SUPERTd_10_1.5'].iloc[-1]
        last_adx = df['ADX_14'].iloc[-1]
        price = df['close'].iloc[-1]
        
        # SYNC & FLIP LOGIC
        delta_executor.sync_delta_position()
        active_symbol = db.get_param("crypto_active_symbol", "")
        
        has_bullish = ("-C-" in active_symbol) or ("CALL" in active_symbol.upper())
        has_bearish = ("-P-" in active_symbol) or ("PUT" in active_symbol.upper())
        has_nothing = not active_symbol or "PAPER" in active_symbol
        
        # Dashboard Line
        sig_text = "BUY" if last_st == 1 else "SELL"
        # print(f"  > BTC 5M: ${price:.2f} | Signal: {sig_text} | ADX: {last_adx:.1f} | Pos: {active_symbol or 'NONE'}")

        if last_adx > 15:
            if last_st == 1 and (has_nothing or has_bearish):
                log_terminal(f"CRYPTO 5M FLIP: BUY BTC @ ${price}", "TRADE")
                delta_executor.execute_crypto_trade(asset, "BUY")
            elif last_st == -1 and (has_nothing or has_bullish):
                log_terminal(f"CRYPTO 5M FLIP: SELL BTC @ ${price}", "TRADE")
                delta_executor.execute_crypto_trade(asset, "SELL")

        crypto_roller.check_and_roll_crypto()
    except Exception as e:
        log_terminal(f"Crypto Error: {e}", "ERROR")

def main():
    clear_terminal()
    print("="*50)
    print("      🌌 BHARAT ALGOVERSE v2.0 - STEALTH MODE 🌌      ")
    print("="*50)
    print("Running on Termux (Android). Terminal Dashboard Active.")
    print("Press Ctrl+C to stop.")
    print("-" * 50)

    while True:
        try:
            run_nifty_slot("agg", 10, 1, "15m")
            run_nifty_slot("sur", 10, 2, "15m")
            run_crypto_master()
            
            # Print a simple heartbeat every minute
            if datetime.datetime.now().second < 30:
                pass # Just keep loop moving
                
            time.sleep(30)
        except KeyboardInterrupt:
            print("\nStopped by User.")
            break
        except Exception as e:
            log_terminal(f"Global Loop Error: {e}", "ERROR")
            time.sleep(10)

if __name__ == "__main__":
    main()
