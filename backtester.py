import pandas as pd
import numpy as np
import logic
import db
import os

def fetch_historical_data(timeframe, days=365):
    """
    Mock function to simulate fetching 1 year of historical data from Upstox.
    In production, this will hit the Upstox Historical Data API.
    """
    num_candles = 10000
    # Generate dates
    date_rng = pd.date_range(end=pd.Timestamp.now(), periods=num_candles, freq='15min')
    
    # Generate realistic-looking price action (Random Walk)
    np.random.seed(42) # Fixed seed for stable backtest demo
    returns = np.random.normal(0, 0.001, num_candles)
    price = 22000 * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame(index=date_rng)
    df['open'] = price
    df['high'] = price + np.random.uniform(5, 20, num_candles)
    df['low'] = price - np.random.uniform(5, 20, num_candles)
    df['close'] = price + np.random.normal(0, 10, num_candles)
    
    return df

def run_backtest(period, multiplier, timeframe):
    """
    Runs the Supertrend strategy on historical data and calculates core metrics.
    """
    df = fetch_historical_data(timeframe)
    
    # Temporarily override db params to ensure logic.py uses requested values
    db.set_param('st_period', period)
    db.set_param('st_multiplier', multiplier)
    
    df_st = logic.calculate_supertrend(df)
    
    dir_col = f"SUPERTd_{int(period)}_{float(multiplier)}"
    
    if dir_col not in df_st.columns:
        return {"error": "Calculation Failed"}
        
    trades = []
    in_position = False
    entry_price = 0.0
    direction = None
    
    # Vectorized shift to find trend flips
    df_st['prev_dir'] = df_st[dir_col].shift(1)
    
    for idx, row in df_st.dropna().iterrows():
        prev_dir = row['prev_dir']
        last_dir = row[dir_col]
        
        signal = "WAIT"
        if prev_dir == -1 and last_dir == 1:
            signal = "BUY"
        elif prev_dir == 1 and last_dir == -1:
            signal = "SELL"
            
        if signal in ["BUY", "SELL"]:
            if in_position:
                # Close old position
                exit_price = row['close']
                raw_pnl = (exit_price - entry_price) if direction == "BUY" else (entry_price - exit_price)
                # Options estimation: PnL * Delta(0.35) * LotSize(50)
                options_pnl = raw_pnl * 0.35 * 50
                trades.append({
                    "Date": idx,
                    "Action": f"EXIT {direction}",
                    "Price": round(exit_price, 2),
                    "PnL": round(options_pnl, 2)
                })
                in_position = False
                
            # Open new position
            entry_price = row['close']
            direction = signal
            in_position = True
            trades.append({
                "Date": idx,
                "Action": f"ENTRY {direction}",
                "Price": round(entry_price, 2),
                "PnL": 0.0
            })
            
    trades_df = pd.DataFrame(trades)
    
    if trades_df.empty:
         return {"Total Trades": 0, "Win Rate %": 0, "Total PnL (₹)": 0, "Max Drawdown (₹)": 0, "Report": "No trades generated."}
    
    # Calculate performance metrics
    exits = trades_df[trades_df['PnL'] != 0.0]
    total_trades = len(exits)
    winning_trades = len(exits[exits['PnL'] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    total_pnl = exits['PnL'].sum()
    
    # Drawdown calculation
    cumulative = exits['PnL'].cumsum()
    peak = cumulative.cummax()
    drawdown = peak - cumulative
    max_drawdown = drawdown.max()
    
    # Save CSV Report
    os.makedirs('reports', exist_ok=True)
    csv_path = 'reports/backtest_report.csv'
    trades_df.to_csv(csv_path, index=False)
    
    return {
        "Total Trades": total_trades,
        "Win Rate %": round(win_rate, 2),
        "Total PnL (₹)": round(total_pnl, 2),
        "Max Drawdown (₹)": round(max_drawdown, 2),
        "Report": f"Detailed log saved to {csv_path}"
    }
