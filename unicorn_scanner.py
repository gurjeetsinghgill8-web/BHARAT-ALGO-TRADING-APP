import time
import json
import os
import pandas as pd
import requests
from datetime import datetime, timedelta
import pandas_ta as ta

# --- SURGICAL CONFIG ---
SCAN_INTERVAL_HOURS = 6
LOG_FILE = "crypto_paper_trades.csv"
LOCK_FILE = "active_unicorns.json"
DELTA_API_BASE = "https://api.india.delta.exchange"
PAPER_TRADE_INTERVAL_MINS = 5

def fetch_24h_tickers():
    """Fetches 24h ticker data from Delta Exchange to find Unicorns."""
    try:
        url = f"{DELTA_API_BASE}/v2/tickers"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('result', [])
    except Exception as e:
        print(f"Error fetching tickers: {e}")
    return []

def get_blasting_unicorns():
    """
    Delta Exchange se top momentum coins dhundta hai
    Filter criteria: 24h Vol > $500,000, 24h Price Change > 8%
    """
    tickers = fetch_24h_tickers()
    unicorns = []
    
    for t in tickers:
        symbol = t.get('symbol', '')
        if not symbol.endswith('USDT'):
            continue
            
        try:
            # Ticker stats
            mark_price = float(t.get('mark_price', 0))
            vol_24h = float(t.get('turnover_24h', 0))  # Turnover usually means quote volume (USDT)
            
            # Some tickers don't have turnover_24h but volume_24h
            if vol_24h == 0:
                vol_24h = float(t.get('volume_24h', 0)) * mark_price
                
            # Price change calculations
            open_24h = float(t.get('open_24h', 0))
            if open_24h > 0:
                change_pct = ((mark_price - open_24h) / open_24h) * 100
            else:
                change_pct = 0
                
            # Filters
            if vol_24h > 500000 and change_pct > 8:
                unicorns.append({
                    "symbol": symbol,
                    "change": change_pct,
                    "volume": vol_24h,
                    "price": mark_price,
                    "status": "OPEN", # Default simulated status
                    "entry_price": 0,
                    "current_position": "NONE"
                })
        except Exception as e:
            continue
            
    # Sort by highest price change first and pick top 3
    unicorns.sort(key=lambda x: x['change'], reverse=True)
    top_3 = unicorns[:3]
    
    if not top_3:
        print("No unicorns found. Returning fallback dummy data for testing.")
        return [
            {"symbol": "SOLUSDT", "change": 12.5, "volume": 2000000, "price": 142.50, "current_position": "NONE", "entry_price": 0},
            {"symbol": "PEPEUSDT", "change": 15.2, "volume": 1500000, "price": 0.0000095, "current_position": "NONE", "entry_price": 0},
            {"symbol": "WIFUSDT", "change": 9.1, "volume": 800000, "price": 3.12, "current_position": "NONE", "entry_price": 0}
        ]
        
    return top_3

def manage_unicorns():
    """
    6-ghante ka lock manage karta hai
    """
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                data = json.load(f)
                last_scan = datetime.fromisoformat(data['timestamp'])
                
                # Agar 6 ghante nahi huye, toh purane coins hi chalao
                if datetime.now() < last_scan + timedelta(hours=SCAN_INTERVAL_HOURS):
                    print(f"🕒 Coins Locked. Next scan in: {last_scan + timedelta(hours=SCAN_INTERVAL_HOURS) - datetime.now()}")
                    return data['coins']
        except Exception as e:
            print(f"Error reading lock file: {e}. Rescanning.")
    
    # Naya scan karo agar 6 ghante ho gaye hain
    print("🔍 6 Hours passed (or no lock)! Scanning for new Unicorns...")
    new_coins = get_blasting_unicorns()
    
    with open(LOCK_FILE, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "coins": new_coins
        }, f)
    return new_coins

def save_unicorns_state(coins):
    """Saves the current state of unicorns (positions) to lock file."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                data = json.load(f)
            data['coins'] = coins
            with open(LOCK_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            pass

def fetch_delta_candles(symbol, resolution="5m", limit=100):
    """Fetches OHLC data directly from Delta Exchange."""
    end_ts = int(time.time())
    start_ts = end_ts - (int(limit) * 300) 
    
    url = f"{DELTA_API_BASE}/v2/history/candles"
    params = {
        "symbol": symbol, 
        "resolution": resolution, 
        "start": start_ts, 
        "end": end_ts
    }
    
    try:
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json().get('result', [])
            if data:
                df = pd.DataFrame(data)
                rename_map = {'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume', 't': 'time'}
                df = df.rename(columns=rename_map)
                
                for col in ['open', 'high', 'low', 'close']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col])
                
                if 'time' in df.columns:
                    df = df.sort_values('time', ascending=True)
                else:
                    df = df.iloc[::-1]
                    
                return df.reset_index(drop=True)
    except Exception as e:
        print(f"Error fetching candles for {symbol}: {e}")
    return pd.DataFrame()

def log_trade(coin_name, entry_price, exit_price, pnl_pct, status, direction):
    """Saves simulated trade to CSV."""
    trade_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "coin": coin_name,
        "direction": direction,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "pnl_pct": pnl_pct,
        "status": status
    }
    
    df_new = pd.DataFrame([trade_data])
    
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        df = pd.concat([df, df_new], ignore_index=True)
    else:
        df = df_new
        
    df.to_csv(LOG_FILE, index=False)
    print(f"📝 Simulated Trade Logged: {coin_name} | {direction} | Entry: {entry_price} | PnL: {pnl_pct}% | {status}")

def paper_trade_logic(coin):
    """
    Paper trade execute karta hai (Sirf Logs)
    Uses Supertrend (SAR) logic on iloc[-2]
    """
    symbol = coin['symbol']
    df = fetch_delta_candles(symbol, resolution="5m", limit=50)
    
    if df.empty or len(df) < 20:
        print(f"Not enough data for {symbol}")
        return coin
        
    try:
        # Calculate Supertrend using pandas_ta (10, 1.5 default)
        st = ta.supertrend(df['high'], df['low'], df['close'], length=10, multiplier=1.5)
        if st is None or st.empty:
            return coin
            
        df = pd.concat([df, st], axis=1)
        
        # We need iloc[-2] (last closed candle)
        last_closed = df.iloc[-2]
        current_price = df.iloc[-1]['close'] # Live approximate price
        
        # Columns in pandas_ta supertrend: SUPERT_10_1.5, SUPERTd_10_1.5
        st_dir_col = [c for c in df.columns if c.startswith('SUPERTd_')][0]
        st_val_col = [c for c in df.columns if c.startswith('SUPERT_')][0]
        
        signal_dir = last_closed[st_dir_col] # 1 for Bull, -1 for Bear
        sar_val = last_closed[st_val_col]
        close_price = last_closed['close']
        
        current_pos = coin.get('current_position', 'NONE')
        entry_price = float(coin.get('entry_price', 0))
        
        print(f"🔍 {symbol} Check -> Pos: {current_pos}, Close[-2]: {close_price:.4f}, SAR: {sar_val:.4f}, Dir: {signal_dir}")
        
        # Logic: If Price > SAR AND no Buy position
        if signal_dir == 1 and current_pos != "BUY":
            # Close Sell if any
            if current_pos == "SELL":
                pnl = ((entry_price - current_price) / entry_price) * 100
                log_trade(symbol, entry_price, current_price, round(pnl, 2), "CLOSED", "SELL")
                
            # Open Buy
            coin['current_position'] = "BUY"
            coin['entry_price'] = current_price
            coin['status'] = "OPEN"
            log_trade(symbol, current_price, None, 0.0, "OPEN", "BUY")
            
        # Logic: If Price < SAR AND no Sell position
        elif signal_dir == -1 and current_pos != "SELL":
            # Close Buy if any
            if current_pos == "BUY":
                pnl = ((current_price - entry_price) / entry_price) * 100
                log_trade(symbol, entry_price, current_price, round(pnl, 2), "CLOSED", "BUY")
                
            # Open Sell
            coin['current_position'] = "SELL"
            coin['entry_price'] = current_price
            coin['status'] = "OPEN"
            log_trade(symbol, current_price, None, 0.0, "OPEN", "SELL")
            
        # Update live PnL if open
        if coin['current_position'] == "BUY":
            coin['live_pnl'] = round(((current_price - float(coin['entry_price'])) / float(coin['entry_price'])) * 100, 2)
        elif coin['current_position'] == "SELL":
            coin['live_pnl'] = round(((float(coin['entry_price']) - current_price) / float(coin['entry_price'])) * 100, 2)
        else:
            coin['live_pnl'] = 0.0
            
    except Exception as e:
        print(f"Error in paper trade logic for {symbol}: {e}")
        
    return coin

if __name__ == "__main__":
    print("🚀 BHARAT ALGOVERSE - UNICORN SCANNER 🦄 STARTED")
    print("Isolation Mode: Running independently.")
    
    while True:
        try:
            active_coins = manage_unicorns()
            updated_coins = []
            
            for coin in active_coins:
                updated_coin = paper_trade_logic(coin)
                updated_coins.append(updated_coin)
                
            save_unicorns_state(updated_coins)
            
            # Wait for 5 minutes (300 seconds) before next paper trade check
            print(f"💤 Sleeping for {PAPER_TRADE_INTERVAL_MINS} minutes...")
            time.sleep(PAPER_TRADE_INTERVAL_MINS * 60)
            
        except Exception as e:
            print(f"⚠️ Blaster Error: {e}")
            time.sleep(30)
