# HYBRID KING — OFFICIAL TRADING RULEBOOK
## The Lowest Drawdown, Highest Consistency Crypto Strategy
### Backtested: 12 Months | Win Rate: 48.6% | Annual ROI: 832% | Max Drawdown: -52%

---

## STRATEGY OVERVIEW

The HYBRID KING uses **3 filters** working together. A trade is ONLY taken when all 3 say "GO":

```
FILTER 1: Supertrend (10, 1.5)  →  Tells DIRECTION (Buy CE or Buy PE)
FILTER 2: ADX > 25              →  Confirms TREND EXISTS (skip sideways)
FILTER 3: RSI Confirmation      →  Confirms MOMENTUM is not exhausted
```

All 3 must align = TRADE. Even 1 missing = SIT AND WAIT.

---

## THE 10 RULES

### RULE 1: ASSET
- **Trade ONLY:** Bitcoin (BTC) Options
- **Never trade:** ETH or any altcoin (ETH lost money on same strategy)

### RULE 2: TIMEFRAME
- **Chart:** 1 Hour candles
- **Check:** Every hour when candle closes
- **Never use:** 15 min or 30 min (proven loss-makers)

### RULE 3: INDICATORS SETUP (On 1H Chart)
```
Indicator 1:  Supertrend     →  Period: 10,  Multiplier: 1.5
Indicator 2:  ADX            →  Period: 14,  Threshold: 25
Indicator 3:  RSI            →  Period: 14
```

### RULE 4: BUY CALL (CE) — All 3 Conditions MUST be TRUE

| Filter | Condition | Why |
|--------|-----------|-----|
| Supertrend | Direction flips from RED (-1) to GREEN (+1) | Market turning bullish |
| ADX | Value is ABOVE 25 | Trend is strong, not sideways |
| RSI | Value is BELOW 65 | Momentum still has room to run UP |

```
IF   Supertrend flips to GREEN
AND  ADX > 25
AND  RSI < 65
THEN → BUY CALL OPTION (CE)
```

### RULE 5: BUY PUT (PE) — All 3 Conditions MUST be TRUE

| Filter | Condition | Why |
|--------|-----------|-----|
| Supertrend | Direction flips from GREEN (+1) to RED (-1) | Market turning bearish |
| ADX | Value is ABOVE 25 | Trend is strong, not sideways |
| RSI | Value is ABOVE 35 | Momentum still has room to run DOWN |

```
IF   Supertrend flips to RED
AND  ADX > 25
AND  RSI > 35
THEN → BUY PUT OPTION (PE)
```

### RULE 6: WHEN NOT TO TRADE (WAIT MODE)
- ADX is below 25 → Market is SIDEWAYS, no trend = no trade
- RSI > 65 on a CE signal → Market already overbought, late entry
- RSI < 35 on a PE signal → Market already oversold, late entry
- If ANY one filter fails → DO NOT TRADE, wait for next signal

### RULE 7: OPTION SELECTION

| Parameter | Setting |
|-----------|---------|
| **Strike** | ATM (At The Money) or 1 strike ITM |
| **Expiry** | 3 Days Away (nearest weekly) |
| **Delta** | 0.50 — 0.60 range |
| **Never buy** | Deep OTM (cheap options = waste of money) |

### RULE 8: EXIT RULES
- **Primary Exit:** When Supertrend flips in OPPOSITE direction
- **On Exit:** Check if new signal qualifies (ADX + RSI). If yes, enter new trade. If no, go to WAIT mode.
- **No Stop Loss needed:** Option premium IS your max loss ($500)

### RULE 9: RISK & POSITION SIZING

| Parameter | Value |
|-----------|-------|
| **Minimum Capital** | $5,000 |
| **Max Risk Per Trade** | $500 (the premium) = 10% of capital |
| **Position Size** | 1 lot per $5,000 capital |
| **Scaling** | $10K = 2 lots, $20K = 4 lots, $50K = 10 lots |
| **Max Open Positions** | 1 at a time (never stack trades) |

### RULE 10: PSYCHOLOGY & DISCIPLINE
- **Max consecutive losses expected:** 6 trades (this is NORMAL)
- **Never turn off** the algo after 3-4 losses
- **Never manually override** the system mid-trade
- **Review:** Monthly only, not daily
- **Never change parameters** without full 12-month backtest

---

## BACKTESTED PERFORMANCE (12 Months BTC)

```
Total Trades:          138 (~11 per month, ~1 every 2-3 days)
Win Rate:              48.6% (almost 1 in 2 trades profit)
Annual P&L:            +$41,606
Annual ROI:            +832% (on $5,000 capital)
Avg Monthly ROI:       +69.3%
Profitable Months:     10 out of 12
Max Drawdown:          -52.4% (LOWEST of all strategies tested)
Max Losing Streak:     6 trades
```

## WHY HYBRID KING BEATS EVERYTHING ELSE

| vs Strategy | HYBRID KING Advantage |
|-------------|----------------------|
| vs ADX Filter | 18% less drawdown (-52% vs -71%), higher win rate (48% vs 43%) |
| vs Stable Wealth (EMA200) | 2x more profit ($41K vs $20K), half the drawdown (-52% vs -112%) |
| vs Plain Supertrend | 3x less drawdown (-52% vs -178%), more consistent months |
| vs ALL Spot strategies | Spot strategies ALL lost money. Options = only profitable approach |

## FLOW CHART: DECISION PROCESS

```
Every 1 Hour (Candle Close):
│
├─ Did Supertrend FLIP direction?
│   ├─ NO  → Do nothing. Hold current position or stay in WAIT.
│   └─ YES → Check ADX...
│            ├─ ADX < 25? → WAIT. No trade. Market is sideways.
│            └─ ADX >= 25? → Check RSI...
│                           ├─ CE Signal + RSI > 65? → SKIP. Overbought.
│                           ├─ PE Signal + RSI < 35? → SKIP. Oversold.
│                           └─ RSI in safe zone? → EXECUTE TRADE!
│                                                   Buy ATM Option
│                                                   3-Day Expiry
│                                                   Hold until next flip
```

---

## DISCLAIMER
Past performance does not guarantee future results. Always start with paper trading.
Real markets include slippage, liquidity gaps, and black swan events.
Never risk money you cannot afford to lose.
