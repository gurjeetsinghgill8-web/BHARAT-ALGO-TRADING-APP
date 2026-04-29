"""
main_loop.py - The Heart of Algoverse (Nifty & Crypto)
======================================================
- Handles Nifty (9:15-15:30 IST)
- Handles Crypto (24/7)
- 2% Daily Loss Protection (Nifty only)
"""

import time
import datetime
import yfinance as yf
import logic
import executor
import delta_executor
import db
import pytz

def send_alert(message):
    print(f"🔔 ALERT: {message}")

def run_nifty_cycle():
    """Logic for Nifty 50 Trading."""
    now = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    
    # Market Hours Check
    if not (now.hour == 9 and now.minute >= 15) and not (9 < now.hour < 15) and not (now.hour == 15 and now.minute <= 30):
        return

    algo_running = db.get_param('algo_running', 'OFF')
    if algo_running == 'OFF':
        return

    # Fetch Data
    timeframe = db.get_param('timeframe', '15m')
    df = yf.download("^NSEI", period="5d", interval=timeframe, progress=False)
    if df.empty: return

    df.columns = [c.lower() for c in df.columns]
    df_st = logic.calculate_supertrend(df)
    signal = logic.get_signal(df_st)
    spot_price = df['close'].iloc[-1]

    if signal in ["BUY", "SELL"]:
        msg = f"🎯 NIFTY SIGNAL: {signal} @ {spot_price}. Executing..."
        send_alert(msg)
        executor.place_order(signal, spot_price)

def run_crypto_cycle():
    """Logic for Crypto Trading (24/7)."""
    crypto_running = db.get_param('crypto_algo_running', 'OFF')
    if crypto_running == 'OFF':
        return

    # ONLY trade BTC as per HYBRID KING rules
    asset_choice = "BTC" 
    symbol = "BTC-USD"
    
    # Fetch Data (Crypto is 24/7, 1H timeframe)
    df = yf.download(symbol, period="5d", interval="1h", progress=False)
    if df.empty: return

    df.columns = [str(c).lower() for c in df.columns]
    
    # Calculate indicators
    df_st = logic.calculate_supertrend(df)
    df_st['adx'] = logic.calculate_adx(df_st, 14)
    df_st['rsi'] = logic.calculate_rsi(df_st['close'], 14)
    
    # ADX FILTER signal logic (Supertrend flip + ADX)
    signal = logic.get_signal(df_st)
    
    if signal in ["BUY", "SELL"]:
        msg = f"🌌 ADX FILTER SIGNAL ({asset_choice}): {signal}. Executing ATM Strategy..."
        send_alert(msg)
        delta_executor.execute_crypto_trade(asset_choice, signal)

def main():
    send_alert("🚀 Algoverse Engine Started (Nifty + Crypto)")
    
    while True:
        try:
            # 1. Run Nifty Logic
            run_nifty_cycle()
            
            # 2. Run Crypto Logic
            run_crypto_cycle()
            
            # Wait 60 seconds before next scan
            time.sleep(60)
            
        except Exception as e:
            send_alert(f"⚠️ System Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
