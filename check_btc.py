import yfinance as yf
import logic
import pandas as pd

df = yf.download('BTC-USD', period='2d', interval='1h', progress=False)
if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
df.columns = [str(c).lower() for c in df.columns]

df = logic.calculate_supertrend(df, period=10, multiplier=1.5)
df = logic.calculate_adx(df)
print(f"BTC Spot: {df['close'].iloc[-1]:.2f}")
print(f"Last Signal: {df['SUPERTd_10_1.5'].iloc[-1]}")
print(f"ADX (14): {df['ADX_14'].iloc[-1]:.2f}")
print(f"Time: {df.index[-1]}")
