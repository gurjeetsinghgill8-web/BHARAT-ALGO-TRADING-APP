import time
import datetime
import requests
import pandas as pd
import db
import logic
import executor
import delta_executor
import crypto_roller
import os
import sys

# --- RISK CONFIG ---
DAILY_LOSS_LIMIT_PCT = 2.0

def fetch_delta_candles(symbol, resolution, limit=100):
    try:
        url = "https://api.india.delta.exchange/v2/history/candles"
        params = {
            "symbol": f"MARK:{symbol}USDT",
            "resolution": resolution,
            "limit": limit
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get('result', [])
            if not data: return pd.DataFrame()
            df = pd.DataFrame(data)
            df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
            return df
    except: pass
    return pd.DataFrame()

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
    
    # AGGRESSIVE: Notify Telegram for everything important
    if type in ["TRADE", "ALERT", "ERROR", "START"]:
        send_telegram_msg(full_msg)

def run_crypto_surgical():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF': return
    if db.get_daily_loss() <= -DAILY_LOSS_LIMIT_PCT:
        log_terminal("RISK LIMIT: Trading Suspended.", "ALERT")
        return

    asset = db.get_param('crypto_asset', 'BTC')
    try:
        df = fetch_delta_candles(asset, "5m", limit=100)
        if df.empty: return
        
        # PURE SUPERTREND 10/1.5 (NO OTHER FILTERS)
        df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
        last_st = df['SUPERTd_10_1.5'].iloc[-1]
        price = df['close'].iloc[-1]
        
        delta_executor.sync_delta_position()
        active_symbol = db.get_param("crypto_active_symbol", "")
        
        has_bullish = ("-C-" in active_symbol) or ("CALL" in active_symbol.upper())
        has_bearish = ("-P-" in active_symbol) or ("PUT" in active_symbol.upper())
        has_nothing = not active_symbol or "PAPER" in active_symbol

        # AGGRESSIVE ENTRY: Immediate execution if signal exists and no position
        if last_st == 1 and (has_nothing or has_bearish):
            log_terminal(f"AGGRESSIVE BUY: {asset} @ ${price}", "TRADE")
            delta_executor.execute_crypto_trade(asset, "BUY")
        elif last_st == -1 and (has_nothing or has_bullish):
            log_terminal(f"AGGRESSIVE SELL: {asset} @ ${price}", "TRADE")
            delta_executor.execute_crypto_trade(asset, "SELL")

        crypto_roller.check_and_roll_crypto()
    except Exception as e:
        log_terminal(f"Crypto Error: {e}", "ERROR")

def main():
    print("="*60)
    print("      🚀 BHARAT ALGOVERSE v2.0 - VOCAL AGGRESSIVE MODE 🚀      ")
    print("="*60)
    
    if not db.load_secrets():
        sys.exit(1)
        
    # 1. Telegram Greeting
    log_terminal("System Started & Monitoring BTC....", "START")
    print("-" * 60)

    delta_executor.sync_delta_position()
    db.set_param('crypto_algo_running', 'ON')
    db.set_param('crypto_asset', 'BTC')
    
    last_heartbeat = time.time()
    
    while True:
        try:
            executor.check_and_roll_nifty()
            run_crypto_surgical()
            
            # 3. Continuous Heartbeat (60s)
            if time.time() - last_heartbeat > 60:
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [HEARTBEAT] Bot is searching...")
                last_heartbeat = time.time()
                
            time.sleep(10) # Fast 10s check
        except KeyboardInterrupt: break
        except Exception as e:
            log_terminal(f"Master Error: {e}", "ERROR")
            time.sleep(10)

if __name__ == "__main__":
    main()
