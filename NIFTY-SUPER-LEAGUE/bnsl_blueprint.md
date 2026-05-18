# 🏦 BANK NIFTY SUPER LEAGUE (BNSL) v1.0 — BLUEPRINT
### Research-Backed | Zero-Conflict Architecture | Lego System

---

## ✅ STEP 0 — NSL v4.2 SEALED (Restore Point)

```
Snapshot folder: NIFTY-SUPER-LEAGUE/NSL_STABLE_V4_2_HEARTBEAT_FIXED/
Sealed: 2026-05-18
Contains: All 9 modules — nsl_engine.py, nsl_utils.py (v4.2 heartbeat fixed)
GitHub: commit c78d193 on master
```
> ⚠️ Is folder ko kabhi edit mat karna. Agar kuch toote → yahan se restore karo.

---

## 📊 BANK NIFTY — RESEARCH FACTS (Verified)

| Parameter | Value | Source |
|-----------|-------|--------|
| **Lot Size** | **30 units** | NSE (revised Jan 2026, was 35) |
| **Expiry Type** | **Monthly ONLY** | SEBI directive — weekly discontinued Nov 20, 2024 |
| **Expiry Day** | **Last Tuesday of month** | NSE standardized |
| **Holiday rule** | Previous trading day | NSE rule |
| **Weekly?** | ❌ NONE | Discontinued permanently |
| **Premium Range** | ₹180 – ₹250 (lower side) | User defined |
| **SuperTrend** | Same — Period=10, Mult=1.0 | User confirmed |
| **Candle** | 5-minute (same) | User confirmed |

---

## 🏗️ ARCHITECTURE DECISION — FULL CLONE (Recommended)

### Option A: Full Clone (Separate Folder) ✅ RECOMMENDED
```
BHARAT ALGO-TRADING/
├── NIFTY-SUPER-LEAGUE/     ← Nifty (LIVE — untouched)
│   └── Port: 8502 | DB: nsl_trader.db | Service: nsl_engine
│
└── BANKNIFTY-SUPER-LEAGUE/ ← Bank Nifty (NEW)
    └── Port: 8504 | DB: bnsl_trader.db | Service: bnsl_engine
```

**Why this is best:**
- ✅ Zero shared state — dono ke DB alag, engine alag
- ✅ One crashes → dusra chalti rehti hai
- ✅ Different lot sizes, different premium range — no config conflict
- ✅ VPS pe dono separately restart karo
- ✅ Telegram messages alag prefix se (NSL vs BNSL)
- ✅ Restore karna easy — ek ka snapshot dusre ko affect nahi karta

### Option B: Shared Codebase (Multi-instrument) ❌ NOT RECOMMENDED
- Config mismatch risk — ek parameter change dono ko affect kare
- Debug karna mushkil — kahan se aaya error?
- "Aapas mein class karna" — exactly yahi problem hogi

---

## 📐 BNSL vs NSL — KEY DIFFERENCES TABLE

| Parameter | NSL (Nifty) | BNSL (Bank Nifty) |
|-----------|-------------|-------------------|
| Instrument | NIFTY 50 | BANK NIFTY |
| Upstox Key | `NSE_INDEX\|Nifty 50` | `NSE_INDEX\|Nifty Bank` |
| Lot Size | **65** | **30** |
| Premium Range | ₹80 – ₹160 | ₹180 – ₹250 |
| Expiry | Weekly (Tue) | **Monthly (last Tue)** |
| Port | 8502 | **8504** |
| DB File | nsl_trader.db | **bnsl_trader.db** |
| Service | nsl_engine | **bnsl_engine** |
| Telegram Prefix | `🏆 NSL` | `🏦 BNSL` |
| SuperTrend | 10 / 1.0 | **Same: 10 / 1.0** |
| Candle | 5-min | **Same: 5-min** |
| Start Time | 9:16 AM | **Same: 9:16 AM** |
| End Time | 3:00 PM | **Same: 3:00 PM** |

---

## 🧱 BUILD PLAN — 3 Phases, Lego by Lego

### Phase 1 — Clone + Config (2 bricks)
```
Brick 1: Clone NIFTY-SUPER-LEAGUE → BANKNIFTY-SUPER-LEAGUE
Brick 2: Edit bnsl_config.py — all BNSL-specific constants
         (instrument key, lot size=30, premium range, port, DB name)
```

### Phase 2 — Expiry Logic (1 brick)
```
Brick 3: Edit bnsl_executor.py — monthly expiry selection
         (Bank Nifty = last Tuesday of month, NOT weekly)
         Current NSL finds next Thu expiry → BNSL finds last Tue of month
```

### Phase 3 — Deploy (2 bricks)
```
Brick 4: Upload BANKNIFTY-SUPER-LEAGUE to VPS at /root/BNSL/
         Create bnsl_engine.service + bnsl_dashboard.service
Brick 5: Git commit + push
```

---

## ❓ QUESTIONS BEFORE CODE (Answer These)

### Q1 — Same Telegram Bot?
> NSL aur BNSL dono ek hi Telegram chat pe aayein, ya alag-alag?
> **Recommendation:** Same chat (586422450) — sirf prefix alag (`🏆 NSL` vs `🏦 BNSL`)

### Q2 — Same Upstox Account?
> Kya Bank Nifty trading bhi usi Upstox account se hogi?
> (Access token refresh ek hi jagah se hoga)

### Q3 — Lots?
> Bank Nifty mein kitne lots? (Lot size=30 confirmed, but how many lots?)
> NSL mein 1 lot hai — BNSL mein bhi 1 lot?

### Q4 — VPS ready hai?
> VPS pe space aur memory enough hai? (Currently NSL + BTC engine chal rahe hain)

---

## 🔒 RULES — WILL NOT CHANGE

1. NSL files — **ZERO TOUCH** during BNSL build
2. VPS guard — both engines run on `46.224.133.16` only
3. SuperTrend params — Period=10, Mult=1.0 (same as NSL)
4. Exchange = truth — same philosophy
5. One trade at a time per engine — lot guard in both

---

*Blueprint sealed — Awaiting answers to Q1–Q4 before code starts.*
