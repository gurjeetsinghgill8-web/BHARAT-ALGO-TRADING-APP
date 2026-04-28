import pandas_ta as ta
import db

def calculate_supertrend(df):
    # Fetching your custom settings from Memory (db.py)
    # Defaults: Period=10, Multiplier=1.5
    period = int(db.get_param('st_period', 10))
    multiplier = float(db.get_param('st_multiplier', 1.5))
    
    # Standard Supertrend calculation
    st = ta.supertrend(df['high'], df['low'], df['close'], length=period, multiplier=multiplier)
    
    # Combining ST with original data
    df = df.join(st)
    return df

def get_signal(df):
    # Rule: Trigger ONLY on Candle Close
    # We look at the completed candle (index -2) and compare it with the previous one (index -3)
    # to detect a 'Trend Flip'.
    
    last_closed = df.iloc[-2]
    prev_closed = df.iloc[-3]
    
    st_column = f"SUPERT_{int(db.get_param('st_period', 10))}_{float(db.get_param('st_multiplier', 1.5))}"
    
    # Logic for Trend Flip (Buy/Sell)
    if last_closed['close'] > last_closed[st_column] and prev_closed['close'] < prev_closed[st_column]:
        return "BUY"
    elif last_closed['close'] < last_closed[st_column] and prev_closed['close'] > prev_closed[st_column]:
        return "SELL"
    
    return "WAIT"
