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

# --- RISK CONFIG ---
DAILY_LOSS_LIMIT_PCT = 2.0 # 2% Max Daily Loss

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def log_terminal(msg, type="INFO"):
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    icon = "🔹"
    if type == "TRADE": icon = "🟢"
    if type == "ALERT": icon = "🚨"
    if type == "ERROR": icon = "❌"
    
    full_msg = f"[{timestamp}] {icon} {msg}"
    print(full_msg)
    
    if type in ["TRADE", "ALERT", "ERROR"]:
        notifier.send_telegram_msg(full_msg)

def check_risk_management():
    # Basic protection: If daily loss > 2%, stop trading
    current_loss = db.get_daily_loss()
    if current_loss <= -DAILY_LOSS_LIMIT_PCT:
        log_terminal("RISK LIMIT REACHED! Daily loss > 2%. Trading Suspended.", "ALERT")
        return False
    return True

def run_crypto_surgical():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF': return
    if not check_risk_management(): return

    asset = db.get_param('crypto_asset', 'BTC')
    timeframe = "5m" # Fixed for Dr. Saab
    
    try:
        symbol = f"{asset}-USD"
        df = yf.download(symbol, period="1d", interval=timeframe, progress=False)
        if df.empty: return
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
        df = logic.calculate_adx(df)
        
        last_st = df['SUPERTd_10_1.5'].iloc[-1]
        last_adx = df['ADX_14'].iloc[-1]
        price = df['close'].iloc[-1]
        
        delta_executor.sync_delta_position()
        active_symbol = db.get_param("crypto_active_symbol", "")
        
        has_bullish = ("-C-" in active_symbol) or ("CALL" in active_symbol.upper())
        has_bearish = ("-P-" in active_symbol) or ("PUT" in active_symbol.upper())
        has_nothing = not active_symbol or "PAPER" in active_symbol

        if last_adx > 15:
            if last_st == 1 and (has_nothing or has_bearish):
                log_terminal(f"CRYPTO BUY: {asset} @ ${price}", "TRADE")
                delta_executor.execute_crypto_trade(asset, "BUY")
            elif last_st == -1 and (has_nothing or has_bullish):
                log_terminal(f"CRYPTO SELL: {asset} @ ${price}", "TRADE")
                delta_executor.execute_crypto_trade(asset, "SELL")

        crypto_roller.check_and_roll_crypto()
    except Exception as e:
        log_terminal(f"Crypto Loop Error: {e}", "ERROR")

def main():
    clear_terminal()
    print("="*60)
    print("      🚀 BHARAT ALGOVERSE v2.0 - STEALTH COMMAND CENTER 🚀      ")
    print("="*60)
    print("Mode: TERMUX (Mobile) | UI: DISABLED | Alerts: TELEGRAM")
    print("-" * 60)

    # Initial Sync
    delta_executor.sync_delta_position()
    
    while True:
        try:
            # Check Nifty
            executor.check_and_roll_nifty() # Standard rolling
            # Check Crypto (5m Sniper)
            run_crypto_surgical()
            
            time.sleep(30)
        except KeyboardInterrupt:
            print("\nSafe Shutdown.")
            break
        except Exception as e:
            log_terminal(f"Master Error: {e}", "ERROR")
            time.sleep(10)

if __name__ == "__main__":
    main()
