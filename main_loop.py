import time
import sqlite3
import pandas as pd
from datetime import datetime
import requests
import db
import logic
import executor
import numpy as np

# Set your Telegram details here
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"

def send_telegram_alert(message):
    """Sends an alert to your Telegram."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        # In a real setup, uncomment below
        # requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram Alert Failed: {e}")

def get_daily_pnl():
    """Helper function to fetch today's PnL from the db."""
    try:
        conn = sqlite3.connect(db.DB_NAME)
        today = datetime.now().strftime('%Y-%m-%d')
        df = pd.read_sql_query("SELECT total_pnl FROM daily_stats WHERE date = ?", conn, params=(today,))
        conn.close()
        if not df.empty:
            return float(df.iloc[0]['total_pnl'])
    except Exception as e:
        print(f"Error fetching P&L: {e}")
    return 0.0

def fetch_market_data(timeframe):
    """
    Fetches OHLC data from Upstox API for the selected timeframe.
    (Mock implementation for safety; connects to live API in production)
    """
    mock_data = {
        'high': np.random.uniform(22450, 22600, 50),
        'low': np.random.uniform(22400, 22550, 50),
        'close': np.random.uniform(22420, 22580, 50)
    }
    df = pd.DataFrame(mock_data)
    return df

def get_current_nifty_spot():
    """Mock spot price."""
    return 22500.0

def main_loop():
    print("🤖 The Silent Worker (main_loop.py) is running 24/7...")
    send_telegram_alert("✅ Algo Server Started. The Silent Worker is active.")
    
    while True:
        try:
            # 1. Check Algo Status
            algo_status = db.get_param('algo_status', 'OFF')
            
            # 2. Risk Management: Daily Loss Check
            daily_pnl = get_daily_pnl()
            max_loss = float(db.get_param('max_loss_limit', -2000.0))
            
            if daily_pnl <= max_loss and algo_status == 'ON':
                db.set_param('algo_status', 'OFF')
                alert_msg = f"🚨 CRITICAL ALERT: 2% Daily Loss Limit Hit (P&L: {daily_pnl}). System STOPPED to protect capital."
                print(alert_msg)
                send_telegram_alert(alert_msg)
                algo_status = 'OFF'
                
            if algo_status != 'ON':
                # Sleep to save resources
                time.sleep(10)
                continue
                
            # 3. Data Fetching
            timeframe = db.get_param('timeframe', '15m')
            df = fetch_market_data(timeframe)
            spot_price = get_current_nifty_spot()
            
            # 4. Strategy Engine Analysis
            df_with_st = logic.calculate_supertrend(df)
            signal = logic.get_signal(df_with_st)
            
            # 5. Order Execution
            if signal in ["BUY", "SELL"]:
                msg = f"🎯 SIGNAL DETECTED: {signal}! Executing Trade..."
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
                send_telegram_alert(msg)
                
                executor.place_order(direction=signal, spot_price=spot_price)
                
                # Sleep briefly to avoid duplicate firing
                time.sleep(60)
            
            # Fetch data every minute (adjustable)
            time.sleep(60)
            
        except requests.exceptions.RequestException as re:
            print(f"Network/API Error. Auto-reconnecting in 10s... ({re})")
            time.sleep(10)
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Loop Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main_loop()
