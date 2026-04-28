# NIFTY SUPERTREND OPTIONS ALGO - PURE LOGIC
## 1. CORE LOGIC
- Supertrend(period=10, multiplier=1.5) on candle CLOSE.
- Signal triggers ONLY after candle closes. No partial candle noise.
- All parameters (Period, Multiplier, Timeframe) must be adjustable from the UI.

## 2. RISK MANAGEMENT
- Max 1 position at a time. Flip signal -> Exit old + Enter new.
- Max daily loss: 2% of capital -> HALT for the day.
- Square Off Transaction if any entry fails (Safety Switch).

## 3. EXECUTION (As per Screenshots)
- Strike: Nearest OTM (Delta ~0.35) or Spot ± 100-150 points.
- Expiry: Next Week Expiry preferred (Theta safety).
- Order Type: LIMIT Order with configurable 'Buffer' (e.g., 15%).
- Product: Delivery/Intraday (Configurable).
