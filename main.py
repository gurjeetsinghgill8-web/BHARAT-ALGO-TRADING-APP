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
    """Fetches OHLC data directly from Delta Exchange (India)."""
    try:
        # We use spot for analysis to match yfinance behavior
        # Delta Spot symbol for BTC is usually 'BTCUSD' or similar
        # For Supertrend, we use 'MARK:BTCUSD' or similar for reliability
        url = "https://api.india.delta.exchange/v2/history/candles"
        params = {
            "symbol": f"MARK:{symbol}USDT", # Use Mark Price for consistent signals
            "resolution": resolution,
            "limit": limit
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get('result', [])
            if not data: return pd.DataFrame()
            df = pd.DataFrame(data)
            # Standardize columns for logic.py
            df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
            # Convert to numeric
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
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
    
    if type in ["TRADE", "ALERT", "ERROR"]:
        send_telegram_msg(full_msg)

def run_crypto_surgical():
    if db.get_param('crypto_algo_running', 'OFF') == 'OFF': return
    if db.get_daily_loss() <= -DAILY_LOSS_LIMIT_PCT:
        log_terminal("RISK LIMIT: Trading Suspended.", "ALERT")
        return

    asset = db.get_param('crypto_asset', 'BTC')
    try:
        # REPLACED yfinance with Delta API for reliability
        df = fetch_delta_candles(asset, "5m", limit=100)
        if df.empty: 
            # log_terminal(f"Data Error: Could not fetch {asset} from Delta.", "ERROR")
            return
        
        df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
        df = logic.calculate_adx(df)
        
        last_st = df['SUPERTd_10_1.5'].iloc[-1]
        last_adx = df['ADX_14'].iloc[-1]
        price = df['close'].iloc[-1]
        # SYNC & FLIP LOGIC (FILTERS REMOVED: ADX SHUT DOWN)
        delta_executor.sync_delta_position()
        active_symbol = db.get_param("crypto_active_symbol", "")
        
        has_bullish = ("-C-" in active_symbol) or ("CALL" in active_symbol.upper())
        has_bearish = ("-P-" in active_symbol) or ("PUT" in active_symbol.upper())
        has_nothing = not active_symbol or "PAPER" in active_symbol

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
    print("      🚀 BHARAT ALGOVERSE v2.0 - DELTA DIRECT MODE 🚀      ")
    print("="*60)
    
    if not db.load_secrets():
        sys.exit(1)
        
    print("Mode: TERMUX | Data: DELTA DIRECT | Alerts: TELEGRAM")
    print("-" * 60)

    delta_executor.sync_delta_position()
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
