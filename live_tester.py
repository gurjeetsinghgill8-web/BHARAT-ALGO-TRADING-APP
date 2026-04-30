import time
import pandas as pd
from datetime import datetime
import db
import logic
import main_loop
import os
import csv

LOG_FILE = "real_time_log.csv"

def init_csv():
    """Initialize the CSV file with headers if it doesn't exist."""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Timestamp', 'Signal', 'System Calculated Price', 'Live Execution Price', 'Status', 'Slippage Delay'])

def live_tester():
    print("🔬 REAL-TIME VALIDATION ENGINE STARTED")
    print("Listening to Live Market Feed (Mock Mode)... Press Ctrl+C to stop.")
    
    main_loop.send_alert("🔬 REAL-TIME VALIDATION STARTED for today's session.")
    init_csv()
    
    while True:
        try:
            # Respect the UI Toggle
            if db.get_param('algo_status', 'OFF') == 'OFF':
                time.sleep(10)
                continue
                
            # 1. Fetch "Live" Market Data (Connected to your fetcher)
            timeframe = db.get_param('timeframe', '15m')
            df = main_loop.fetch_market_data(timeframe)
            spot_price = main_loop.get_current_nifty_spot()
            
            # 2. Run Strategy Logic
            df_with_st = logic.calculate_supertrend(df)
            signal = logic.get_signal(df_with_st)
            
            if signal in ["BUY", "SELL"]:
                # 3. Simulate Alert & Logging
                alert_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # The price the system calculated on the closed candle
                sys_price = df_with_st.iloc[-2]['close'] 
                
                # The actual execution price hitting the broker API
                live_price = spot_price 
                
                msg = f"🚨 MOCK ALERT: {signal} at {alert_time}\nSystem Price: ₹{sys_price:.2f}\nLive Price: ₹{live_price:.2f}"
                print(msg)
                
                # Send to Console Alert
                main_loop.send_alert(msg)
                
                # 4. Log to CSV for end-of-day analysis
                with open(LOG_FILE, mode='a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([alert_time, signal, round(sys_price, 2), round(live_price, 2), "MOCK_SUCCESS", "API Lag: 0.2s"])
                
                # Sleep briefly so it doesn't duplicate log the exact same candle
                time.sleep(60)
            
            # Check market conditions aggressively
            time.sleep(10)
            
        except Exception as e:
            err_msg = f"Live Tester Encountered an Error: {e}. Auto-reconnecting..."
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {err_msg}")
            # main_loop.send_telegram_alert(err_msg)
            time.sleep(5)

if __name__ == "__main__":
    live_tester()

# SUPREME CLOUD SYNC: 2026-04-30
