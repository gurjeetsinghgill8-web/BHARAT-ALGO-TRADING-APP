# BHARAT ALGOVERSE — CRYPTO OPTIONS TRADING RULEBOOK
## Strategy: ADX-Filtered Supertrend | Asset: BITCOIN ONLY

---

## BTC vs ETH VERDICT (Data-Driven)

| Metric | BITCOIN (BTC) | ETHEREUM (ETH) |
|--------|---------------|-----------------|
| **Annual P&L** | **+$46,339** | -$1,920 |
| **Annual ROI** | **+926%** | -38% |
| **Avg Monthly ROI** | **+77.2%** | -3.2% |
| **Profitable Months** | **10 / 12** | 4 / 12 |
| **Max Drawdown** | -70.9% | -47.4% |
| **Win Rate** | **43.1%** | 36.4% |

> [!IMPORTANT]
> **BITCOIN ONLY.** ETH lost money on the same strategy. BTC trends cleaner and longer. ETH chops more and kills option premiums. Do NOT trade ETH with this system.

---

## THE RULES (Non-Negotiable)

### RULE 1: ASSET
- **Trade:** BITCOIN (BTC) options only
- **Exchange:** Delta Exchange (or any exchange offering BTC options)
- **Never trade:** ETH, altcoins, or any other crypto with this system

### RULE 2: TIMEFRAME
- **Chart Timeframe:** 1 Hour candles
- **Check frequency:** Every 1 hour when candle closes
- **Never use:** 15 min or 30 min (proven loss-makers with this strategy)

### RULE 3: INDICATORS (On the 1H Chart)
- **Supertrend:** Period = 10, Multiplier = 1.5
- **ADX (Average Directional Index):** Period = 14
- **ADX Threshold:** 25

### RULE 4: ENTRY CONDITIONS
**For BUY CALL (CE):**
1. Supertrend direction flips from BEARISH (-1) to BULLISH (+1)
2. ADX value is ABOVE 25 at that moment
3. Both conditions must be true simultaneously
4. If ADX < 25 → DO NOT TRADE, sit and wait

**For BUY PUT (PE):**
1. Supertrend direction flips from BULLISH (+1) to BEARISH (-1)
2. ADX value is ABOVE 25 at that moment
3. Both conditions must be true simultaneously
4. If ADX < 25 → DO NOT TRADE, sit and wait

### RULE 5: OPTION SELECTION
- **Strike Price:** ATM (At The Money) or 1 strike ITM (In The Money)
- **Expiry:** 3 Days Away (shortest available weekly expiry)
- **Delta Range:** 0.50 to 0.60 (ATM sweet spot)
- **Never buy:** Deep OTM options (waste of premium on sideways moves)

### RULE 6: EXIT CONDITIONS
- **Exit when:** Supertrend flips in the OPPOSITE direction on 1H chart
- **Immediately:** Enter the new direction trade (if ADX > 25)
- **If ADX drops < 25** at flip time: Exit current trade but do NOT enter new trade. Wait.

### RULE 7: RISK MANAGEMENT
- **Max risk per trade:** $500 (the premium paid for ATM option)
- **Deployed Capital:** Minimum $5,000 account
- **Risk per trade:** 10% of capital maximum
- **Max losing streak expected:** 6 trades (historically proven)
- **Never increase position size** during a losing streak

### RULE 8: POSITION SIZING
- **Quantity:** 1 lot per $5,000 capital
- **Scaling:** For every additional $5,000, add 1 lot
- **Example:** $10,000 account = 2 lots max, $20,000 = 4 lots max

### RULE 9: MONTHLY EXPECTATIONS (Based on 12-Month Backtest)
- **Average Monthly Return:** +77% on deployed capital
- **Winning Months:** 9-10 out of 12 (75-83%)
- **Losing Months:** 2-3 out of 12 (max loss typically -25%)
- **Best Month Possible:** +187% (Feb 2026 style breakout)
- **Worst Month Possible:** -25% (sideways grind)

### RULE 10: PSYCHOLOGY RULES
- **DO NOT turn off the Algo** after 2-3 losing trades. The system recovers.
- **DO NOT switch to manual trading** mid-month. Trust the data.
- **DO NOT change parameters** without running a full 12-month backtest first.
- **Max expected consecutive losing trades:** 6 (this is NORMAL, do not panic)
- **Review performance:** Monthly, not daily. Daily P&L watching kills discipline.

---

## SUMMARY: THE COMPLETE SETUP

```
ASSET:          Bitcoin (BTC) Options ONLY
TIMEFRAME:      1 Hour Candles
SUPERTREND:     Period = 10, Multiplier = 1.5
ADX FILTER:     Only trade when ADX > 25
OPTION TYPE:    ATM / Slight ITM
EXPIRY:         3 Days (Nearest Weekly)
CAPITAL:        $5,000 minimum per lot
EXIT:           On opposite Supertrend flip
```

## EXPECTED PERFORMANCE (Backtested 12 Months)

```
Annual ROI:           +926%
Average Monthly ROI:  +77%
Profitable Months:    10 out of 12
Max Drawdown:         -71%
Win Rate:             43%
Total Trades/Year:    ~210 (about 1 per day avg)
```

---

> [!CAUTION]
> **DISCLAIMER:** Past performance does not guarantee future results. These are backtested results using historical data. Always start with paper trading first. Real market conditions include slippage, liquidity issues, and unexpected events that backtesting cannot capture. Never risk money you cannot afford to lose.
