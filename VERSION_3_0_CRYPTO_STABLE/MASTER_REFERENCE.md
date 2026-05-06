# 🚀 BHARAT ALGOVERSE v3.0 — Master Reference Document

> **⚠️ FOR ANTIGRAVITY AI:** Ye file **pehle padhni hai** har kaam shuru karne se pehle.  
> Ye ek living document hai — har stable version ke baad update hoti hai.  
> **Sealed backup folders mein kabhi directly edit mat karo.**

---

## 🗂️ Project Location

```
c:\Users\pc\Desktop\gurjas ai\BHARAT ALGO-TRADING\
```

**VPS:** `root@46.224.133.16`  
**Dashboard:** `http://46.224.133.16:8501`  
**GitHub:** `https://github.com/gurjeetsinghgill8-web/BHARAT-ALGO-TRADING-APP`  
**Branch:** `main_temp → main`

---

## 📦 Stable Version Vault

> These folders are **SEALED**. Never edit them. Only read from them for restoration.

| Folder | Version | Module | Status |
|--------|---------|--------|--------|
| `VERSION_3_0_CRYPTO_STABLE/` | v3.0 | Crypto (BTC/Delta) | ✅ LIVE |
| `VERSION_3_0_NIFTY_STABLE/` | v3.0 | Nifty (NSE/Upstox) | ✅ LIVE |
| `VERSION_2_0_FULL_PROOF_BACKUP/` | v2.0 | Both | Legacy |

### How to Restore a Stable Version

```powershell
# Restore Crypto v3.0
Copy-Item "VERSION_3_0_CRYPTO_STABLE\*" "." -Force
.\DEPLOY_NOW.bat

# Restore Nifty v3.0
Copy-Item "VERSION_3_0_NIFTY_STABLE\*" "." -Force
.\DEPLOY_NOW.bat
```

---

## 🏗️ Module Architecture

```
BHARAT ALGOVERSE v3.0
│
├── 🚀 CRYPTO MODULE (Always running, 24x7)
│   ├── main.py           ← Bot loop + janitor + SL/TP monitor
│   ├── logic.py          ← Supertrend signal calculator
│   ├── delta_executor.py ← Delta Exchange API (BTC options)
│   ├── db.py             ← SQLite DB (shared with Nifty)
│   ├── utils.py          ← Telegram + logs (shared)
│   └── Systemd service:  bharat_engine (port lock: 47200)
│
├── 📈 NIFTY MODULE (Market hours: 9:25AM–3:10PM IST only)
│   ├── nifty_main.py     ← Bot loop + SL/TP + SAR flip
│   ├── nifty_logic.py    ← Supertrend via yfinance (NSE data)
│   ├── nifty_executor.py ← Upstox API (option chain + orders)
│   ├── db.py             ← Shared DB (nifty_* key namespace)
│   ├── utils.py          ← Shared Telegram + logs
│   └── Systemd service:  bharat_nifty (port lock: 47201)
│
└── 🖥️ DASHBOARD
    ├── app.py            ← Streamlit (Page 1: Crypto, Page 2: Nifty)
    └── Systemd service:  bharat_dashboard (port 8501)
```

---

## 🔒 Module Isolation Rules (NEVER Break These)

| Rule | Detail |
|------|--------|
| Crypto DB keys | Start with `crypto_`, `trade_`, `st_`, `sl_`, `tp_` |
| Nifty DB keys | ALL start with `nifty_` |
| Crypto files | `main.py`, `logic.py`, `delta_executor.py` — only for Crypto |
| Nifty files | `nifty_*.py` — only for Nifty |
| Shared files | `db.py`, `utils.py`, `app.py`, `requirements.txt` |
| Port locks | Crypto=47200, Nifty=47201 — never swap |
| Exchange APIs | Crypto=Delta Exchange, Nifty=Upstox — never mix |
| Data source | Crypto=Delta API, Nifty=yfinance (free, no subscription) |

---

## 🔑 Secrets Format (secrets.txt — VPS only, never git)

```
DELTA_API_KEY=your_delta_key
DELTA_API_SECRET=your_delta_secret
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
TRADE_MODE=LIVE
UPSTOX_ACCESS_TOKEN=your_upstox_token   ← Required for Nifty LIVE
```

---

## 📊 Key Settings Reference

### Crypto Settings (in DB)

| Key | Default | Description |
|-----|---------|-------------|
| `trade_mode` | LIVE | PAPER or LIVE |
| `candle_timeframe` | 5m | Signal timeframe |
| `crypto_trade_size` | 1 | Lots per trade |
| `st_period` | 10 | Supertrend period |
| `st_multiplier` | 1.5 | Supertrend multiplier |
| `sl_percent` | 40 | Stop loss % |
| `tp_percent` | 100 | Take profit % |

### Nifty Settings (in DB)

| Key | Default | Description |
|-----|---------|-------------|
| `nifty_trade_mode` | LIVE | PAPER or LIVE |
| `nifty_symbol` | ^NSEI | NSE instrument |
| `nifty_timeframe` | 15m | Signal timeframe |
| `nifty_st_period` | 10 | Supertrend period |
| `nifty_st_multiplier` | 1.5 | Supertrend multiplier |
| `nifty_expiry_weekday` | 1 | 0=Mon, 1=Tue, 2=Wed, 3=Thu |
| `nifty_target_premium` | 120 | Target option premium Rs. |
| `nifty_lot_size` | 25 | Nifty lot = 25 units |
| `nifty_sl_percent` | 30 | SL % of entry premium |
| `nifty_tp_percent` | 80 | TP % of entry premium |

---

## 🖥️ VPS Services

```bash
systemctl status bharat_dashboard
systemctl status bharat_engine
systemctl status bharat_nifty

# View live logs
journalctl -u bharat_engine -f
journalctl -u bharat_nifty -f
journalctl -u bharat_dashboard -f
```

---

## 🚀 Deploy Process (One-click)

```powershell
# From Windows laptop:
.\DEPLOY_NOW.bat
```

---

## 📋 Version History

| Date | Version | What Changed |
|------|---------|--------------|
| 2026-05-06 | v3.0 LIVE | Expiry configurable, LIVE mode, Upstox token loader |
| 2026-05-06 | v3.0 Nifty Launch | nifty_logic, nifty_executor, nifty_main, dashboard Page 2 |
| 2026-05-06 | v3.0 Dashboard Fix | Crash-free dashboard, unique chart keys, CSS fix |
| 2026-05-05 | v2.0 | Clean Slate, SL/TP in-code, Auto-Reinvest |
| 2026-04-28 | v1.0 | Initial bot (Termux/Aggressive SAR) |

---

## 🤖 Instructions for Antigravity AI

**6 rules — hamesha follow karo:**

1. **Is file ko pehle padho** — `MASTER_REFERENCE.md` pehle dekho, phir code karo
2. **Sealed folders se sirf padho** — `VERSION_3_0_CRYPTO_STABLE/` aur `VERSION_3_0_NIFTY_STABLE/` — kabhi directly edit mat karo
3. **Modules ko alag rakho** — Nifty code mein crypto touch mat karo, crypto mein Nifty touch mat karo
4. **DB namespace respect karo** — `nifty_*` sirf Nifty ke liye, baki Crypto ke liye
5. **Har stable kaam ke baad sealed folder update karo** — `VERSION_3_0_*` folders mein latest copy raho
6. **Deploy karo, check karo** — Har change ke baad `systemctl is-active` se teen services verify karo

---

*Last updated: 2026-05-06 | Maintained by: Antigravity AI*
*Built with love for Dr. Saab 🩺*
