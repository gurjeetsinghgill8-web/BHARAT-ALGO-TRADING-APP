import sys
sys.path.insert(0, '/root/NSL')
import nsl_db as db
db.init_defaults()
tok = db.get("upstox_access_token")
tg  = db.get("telegram_bot_token")
print(f"Token : {len(tok)} chars" if tok else "Token : MISSING ❌")
print(f"Telegram: OK ✅" if tg else "Telegram: MISSING ❌")
print(f"Setup OK: {db.is_setup_complete()}")
