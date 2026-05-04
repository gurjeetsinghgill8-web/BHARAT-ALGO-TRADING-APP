import db
print(f"API Key: {'PRESENT' if db.get_param('delta_api_key') else 'MISSING'}")
print(f"Trade Mode: {db.get_param('trade_mode')}")
print(f"Crypto Trade Size: {db.get_param('crypto_trade_size')}")
print(f"Crypto Active Symbol: {db.get_param('crypto_active_symbol')}")
