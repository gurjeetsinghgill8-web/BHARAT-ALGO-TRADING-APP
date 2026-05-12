import db
db.load_secrets()

# Fix 1: Expiry — nearest option (1 day min)
db.set_param("expiry_threshold", "1")

# Fix 2: Clear zombie lock completely
db.set_param("local_trade_active", "NO")
db.set_param("active_call_symbol", "NONE")
db.set_param("active_put_symbol", "NONE")
db.set_param("crypto_active_symbol", "NONE")

print("=== VPS DB RESET COMPLETE ===")
print("expiry_threshold :", db.get_param("expiry_threshold"))
print("local_trade_active:", db.get_param("local_trade_active"))
print("active_call :", db.get_param("active_call_symbol"))
print("active_put  :", db.get_param("active_put_symbol"))
print("=============================")
