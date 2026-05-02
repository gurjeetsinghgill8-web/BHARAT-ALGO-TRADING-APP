import db

def setup():
    print("-" * 40)
    print("🌌 BHARAT ALGOVERSE: SECURE KEY SETUP 🌌")
    print("-" * 40)
    print("Warning: Keys are stored LOCALLY on your phone.")
    print("They will NOT be uploaded to GitHub. Safe & Secure.")
    print("-" * 40)
    
    # Delta Keys
    dk = input("Enter Delta API Key: ").strip()
    ds = input("Enter Delta API Secret: ").strip()
    if dk: db.set_param('delta_api_key', dk)
    if ds: db.set_param('delta_api_secret', ds)
    
    # Upstox Keys
    uk = input("Enter Upstox API Key (Skip if N/A): ").strip()
    if uk: db.set_param('upstox_api_key', uk)
    
    # Telegram Alerts
    tt = input("Enter Telegram Bot Token: ").strip()
    tc = input("Enter Telegram Chat ID: ").strip()
    if tt: db.set_param('telegram_bot_token', tt)
    if tc: db.set_param('telegram_chat_id', tc)
    
    # Initial Settings
    db.set_param('crypto_algo_running', 'ON')
    db.set_param('crypto_asset', 'BTC')
    
    print("\n" + "="*40)
    print("✅ KEYS SAVED LOCALLY! You are now safe.")
    print("Run 'python main.py' to start the bot.")
    print("="*40)

if __name__ == "__main__":
    setup()
