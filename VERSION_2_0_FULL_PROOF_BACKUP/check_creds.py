import db
k = db.get_param('delta_api_key', '')
s = db.get_param('delta_api_secret', '')
print(f"Key: {k[:4]}... (Len: {len(k)})")
print(f"Secret: {s[:4]}... (Len: {len(s)})")
print(f"Trade Mode: {db.get_param('trade_mode')}")
