import time
import datetime
import yfinance as yf
import pandas as pd
import db
import logic
import executor
import delta_executor
import crypto_roller
import requests
import os
import sys

# --- RISK CONFIG ---
DAILY_LOSS_LIMIT_PCT = 2.0

def send_telegram_msg(message):
    bot_token = db.get_param('telegram_bot_token', '')
    chat_id = db.get_param('telegram_chat_id', '')
    if bot_token and chat_id:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": f"🚀 BHARAT ALGO:\n{message}"}
            requests.post(url, json=payload, timeout=5)
        except: pass

def log_terminal(msg, type="INFO"):
    timestamp = datetime.datetime.now().strftime('%H:%M:%S')
    icon = "🔹"
    if type == "TRADE": icon = "🟢"
    if type == "ALERT": icon = "🚨"
    if type == "ERROR": icon = "❌"
    
    full_msg = f"[{timestamp}] {icon} {msg}"
    print(full_msg)
    
    if type in ["TRADE", "ALERT", "ERROR"]:
        send_telegram_msg(full_msg)

def run_crypto_surgical():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF': return
    if db.get_daily_loss() <= -DAILY_LOSS_LIMIT_PCT:
        log_terminal("RISK LIMIT: Trading Suspended.", "ALERT")
        return

    asset = db.get_param('crypto_asset', 'BTC')
    try:
        symbol = f"{asset}-USD"
        df = yf.download(symbol, period="1d", interval="5m", progress=False)
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
        log_terminal(f"Crypto Error: {e}", "ERROR")

def main():
    print("="*60)
    print("      🚀 BHARAT ALGOVERSE v2.0 - STEALTH COMMAND CENTER 🚀      ")
    print("="*60)
    
    # --- SECURE SECRETS LOAD ---
    if not db.load_secrets():
        sys.exit(1) # Halt bot if secrets are missing
        
    print("Mode: TERMUX (Mobile) | UI: DISABLED | Alerts: TELEGRAM")
    print("-" * 60)

    delta_executor.sync_delta_position()
    
    # Set default running status
    db.set_param('crypto_algo_running', 'ON')
    db.set_param('crypto_asset', 'BTC')
    
    while True:
        try:
            executor.check_and_roll_nifty()
            run_crypto_surgical()
            time.sleep(30)
        except KeyboardInterrupt: break
        except Exception as e:
            log_terminal(f"Master Error: {e}", "ERROR")
            time.sleep(10)

if __name__ == "__main__":
    main()
