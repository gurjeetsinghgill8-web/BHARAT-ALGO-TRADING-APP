import pandas_ta as ta
import db
import pandas as pd

def calculate_supertrend(df):
    """
    Calculates Supertrend based on user's exact UI parameters (Default 10, 1.5).
    """
    period = int(float(db.get_param('st_period', 10)))
    multiplier = float(db.get_param('st_multiplier', 1.5))
    
    # pandas_ta calculation
    st = ta.supertrend(df['high'], df['low'], df['close'], length=period, multiplier=multiplier)
    
    # Combine original OHLC with Supertrend Data
    df = df.join(st)
    return df

def get_signal(df):
    """
    Checks the exact flip of Supertrend on the LAST CLOSED CANDLE.
    Nifty closing ABOVE Supertrend -> BUY (Call Option)
    Nifty closing BELOW Supertrend -> SELL (Put Option)
    """
    period = int(float(db.get_param('st_period', 10)))
    multiplier = float(db.get_param('st_multiplier', 1.5))
    dir_col = f"SUPERTd_{period}_{multiplier}"
    
    if dir_col not in df.columns:
        return "WAIT"
        
    # We strictly look at the last completed candle (index -2) 
    # and the one before it (index -3) to detect a fresh "Flip".
    # Index -1 is the current running (incomplete) candle, which we ignore.
    
    try:
        last_closed = df.iloc[-2]
        prev_closed = df.iloc[-3]
        
        last_dir = last_closed[dir_col]
        prev_dir = prev_closed[dir_col]
        
        # Trend flipped from Negative (-1) to Positive (1)
        if prev_dir == -1 and last_dir == 1:
            return "BUY" # Hum Call Option (CE) buy karenge
            
        # Trend flipped from Positive (1) to Negative (-1)
        elif prev_dir == 1 and last_dir == -1:
            return "SELL" # Hum Put Option (PE) buy karenge
            
    except Exception as e:
        print(f"Logic Error: {e}")
        
    return "WAIT"
