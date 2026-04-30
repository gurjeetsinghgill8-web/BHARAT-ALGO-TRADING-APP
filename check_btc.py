import yfinance as yf
import logic
import pandas as pd

try:
    df = yf.download('BTC-USD', period='2d', interval='1h', progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    
    df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
    df = logic.calculate_adx(df)
    
    last_row = df.iloc[-1]
    print(f"BTC Spot: {last_row['close']:.2f}")
    print(f"Signal (10/1.5): {'BUY' if last_row['SUPERTd_10_1.5']==1 else 'SELL'}")
    print(f"ADX (14): {last_row['ADX_14']:.2f}")
    print(f"Time: {df.index[-1]}")
except Exception as e:
    print(f"Error: {e}")
