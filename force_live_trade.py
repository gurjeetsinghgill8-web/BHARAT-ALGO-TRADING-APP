import yfinance as yf
import logic
import delta_executor
import db
import pandas as pd
import datetime

def force_trade_now():
    print(f"[{datetime.datetime.now()}] !!! FORCE LIVE TRADE EXECUTION !!!")
    
    # Ensure Live mode
    db.set_param('crypto_mode', 'Live')
    db.set_param('crypto_algo_running', 'ON')
    
    symbol = "BTC-USD"
    print(f"Fetching latest data for {symbol}...")
    df = yf.download(symbol, period="5d", interval="1h", progress=False)
    
    if df.empty:
        print("Error: No data.")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    
    # Calculate indicators
    df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
    df['adx'] = logic.calculate_adx(df, 14)
    
    last_row = df.iloc[-1]
    adx_now = last_row['adx']
    direction = last_row['SUPERTd_10_1.5'] # 1 = BUY, -1 = SELL
    
    print(f"Current Price : {last_row['close']:.2f}")
    print(f"Current ADX   : {adx_now:.2f}")
    print(f"Current Trend : {'Bullish (CE)' if direction == 1 else 'Bearish (PE)'}")
    
    if adx_now >= 20:
        signal = "BUY" if direction == 1 else "SELL"
        print(f"[OK] ADX > 20 and Trend Active. Executing LIVE trade now...")
        delta_executor.execute_crypto_trade("BTC", signal)
        print("Done. Check your Delta Exchange account and Dashboard!")
    else:
        print(f"[SKIP] ADX ({adx_now:.2f}) still below 20. Market is too flat even for a demo.")

if __name__ == "__main__":
    force_trade_now()

# SUPREME CLOUD SYNC: 2026-04-30
