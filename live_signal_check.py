import yfinance as yf
import logic
import delta_executor
import db
import pandas as pd
import datetime

def check_and_execute_now():
    print(f"[{datetime.datetime.now()}] Starting Manual Signal Check...")
    
    # 1. Ensure mode is LIVE for this check if user wants live
    # But for safety in a script, let's just see what the signal IS first
    db.set_param('crypto_mode', 'Live')
    db.set_param('crypto_algo_running', 'ON')
    
    symbol = "BTC-USD"
    print(f"Fetching latest data for {symbol}...")
    df = yf.download(symbol, period="5d", interval="1h", progress=False)
    
    if df.empty:
        print("Error: No data fetched.")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    
    # 2. Calculate Indicators
    df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
    df['adx'] = logic.calculate_adx(df, 14)
    df['rsi'] = logic.calculate_rsi(df['close'], 14)
    
    # 3. Get Signal
    signal = logic.get_signal(df)
    
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    print(f"Current Price : {last_row['close']:.2f}")
    print(f"Current ADX   : {last_row['adx']:.2f}")
    print(f"Current RSI   : {last_row['rsi']:.2f}")
    print(f"Current ST Dir: {'Bullish' if last_row['SUPERTd_10_1.5'] == 1 else 'Bearish'}")
    print(f"Prev ST Dir   : {'Bullish' if prev_row['SUPERTd_10_1.5'] == 1 else 'Bearish'}")
    print(f"Final Signal  : {signal}")
    
    if signal in ["BUY", "SELL"]:
        print(f"🚨 SIGNAL DETECTED! Executing {signal} trade on Delta Exchange...")
        delta_executor.execute_crypto_trade("BTC", signal)
    else:
        print("No fresh crossover signal detected at this candle close. Standing by.")

if __name__ == "__main__":
    check_and_execute_now()
