

# BHARAT ALGO-TRADING SYSTEM LOGIC (Dr. Saab Edition)

## 1. Core Signal Strategy
- **Indicator**: Supertrend
- **Settings**: 10 Period, 1.5 Multiplier
- **Timeframe**: 5 Minutes (5M)
- **Candle Rule**: Always use the **Closed Candle** (Previous Candle) for signals. Never use the running live candle.
  - If `Previous Close > Supertrend`: Signal is **CALL (BUY)**
  - If `Previous Close < Supertrend`: Signal is **PUT (SELL)**

## 2. Execution Rules (The "Lego" System)
- **Timeframe Restriction**: Signal checks occur every 5 minutes on the boundary (e.g., 10:00, 10:05, 10:10).
- **Clean Slate Rule**: Before taking any new trade, the system MUST ensure all existing trades are closed. Square off everything first.
- **Always-In-Trade Rule**: 
  - If the screen is empty (no active trades), immediately check the signal and take a trade.
  - Never leave the screen empty for long.
- **Instrument Selection (Bitcoin BTC)**:
  - **Expiry**: Never take same-day expiry. Use the next day's expiry (Next Day).
  - **Strike**: Choose ATM (At The Money) or slightly OTM (Out of the Money) - 1 strike away.
- **Order Type**: Always use **Market Orders** for closing positions to ensure guaranteed exit.

## 3. Risk Management & Safety
- **Hard Stop Loss**: 40% loss on any active position must trigger an immediate market square-off.
- **Janitor Mode**: A background process (Janitor) runs every 15 seconds to:
  - Retry failed close orders.
  - Ensure no "zombie" positions exist.
  - Match the screen to the target signal.
- **Process Lock**: Single-instance protection (singleton) to prevent multiple bots from running simultaneously.

## 4. Operational Guidelines
- **Retry Logic**: If a trade fails to close, retry every 10-15 seconds.
- **Lot Size**: Controlled via Dashboard (Standard: 3 or 4 lots).
- **Mode**: Supports both PAPER and LIVE modes.
- **Heartbeat**: 30-minute status updates sent to Telegram.
