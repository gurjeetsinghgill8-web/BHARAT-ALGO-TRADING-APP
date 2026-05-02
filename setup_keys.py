import db

def setup():
    print("--- BHARAT ALGOVERSE: KEY SETUP ---")
    
    # Delta Keys
    dk = input("Enter Delta API Key: ")
    ds = input("Enter Delta API Secret: ")
    if dk: db.set_param('delta_api_key', dk)
    if ds: db.set_param('delta_api_secret', ds)
    
    # Upstox (Optional if already set)
    uk = input("Enter Upstox API Key (Press Enter to Skip): ")
    if uk: db.set_param('upstox_api_key', uk)
    
    # Telegram
    tt = input("Enter Telegram Bot Token: ")
    tc = input("Enter Telegram Chat ID: ")
    if tt: db.set_param('telegram_bot_token', tt)
    if tc: db.set_param('telegram_chat_id', tc)
    
    # Strategy
    db.set_param('crypto_algo_running', 'ON')
    db.set_param('crypto_asset', 'BTC')
    
    print("\n[SUCCESS] Keys saved to database! You can now run 'python main.py'.")

if __name__ == "__main__":
    setup()
