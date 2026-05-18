import sqlite3, requests, urllib.parse, sys
conn = sqlite3.connect('/root/NSL/nsl_trader.db')
tok  = conn.execute("SELECT value FROM settings WHERE key='upstox_access_token'").fetchone()
tok  = tok[0] if tok else ''
print(f"Token length: {len(tok)}")

h = {'Authorization': 'Bearer ' + tok, 'Accept': 'application/json'}
key = urllib.parse.quote('NSE_INDEX|Nifty 50', safe='')

# URL1: with fromDate and toDate
url1 = f'https://api.upstox.com/v2/historical-candle/{key}/5minute/2026-05-17/2026-05-17'
r1 = requests.get(url1, headers=h, timeout=10)
print(f'URL1 status: {r1.status_code} | {r1.text[:400]}')

# URL2: toDate only
url2 = f'https://api.upstox.com/v2/historical-candle/{key}/5minute/2026-05-17'
r2 = requests.get(url2, headers=h, timeout=10)
print(f'URL2 status: {r2.status_code} | {r2.text[:400]}')
