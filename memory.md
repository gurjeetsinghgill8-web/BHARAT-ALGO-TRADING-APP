# BHARAT ALGO-TRADING SYSTEM LOGIC (Stable System 2.0)

## 1. Core Signal Strategy
- **Indicator**: Supertrend
- **Settings**: 10 Period, 1.5 Multiplier
- **Timeframe**: 5 Minutes (5M)
- **Candle Rule**: Always use the **Closed Candle** (Previous Candle) for signals. 
  - `iloc[-2]` is used to avoid fluctuation from the live candle.
  - If `Previous Close > Supertrend`: Signal is **BUY (CALL)**.
  - If `Previous Close < Supertrend`: Signal is **SELL (PUT)**.

## 2. Execution Rules (The "Lego" System)
- **Signal Boundary**: Signal is checked every 15 seconds, but it only changes when the 5M candle closes.
- **Clean Slate Rule**: Before taking any new trade, all existing positions must be squared off.
- **Always-In-Trade**: If no trade is active, the bot immediately takes the position indicated by the last closed candle.
- **Instrument (Bitcoin BTC)**:
  - **Expiry**: Never same-day. Uses the nearest expiry that is at least 1 day away.
  - **Strike**: ATM or 1-strike OTM (Offset=1).
- **Order Type**: Always use **Market Orders** for both Entry and Exit to ensure execution.
- **Quantity Guard**: Maximum **1 lot** (Temporary for stability testing).

## 3. Risk Management & Safety
- **Hard Stop Loss**: 40% loss on entry value triggers an immediate market square-off.
- **Janitor Mode**: Runs every 15 seconds to enforce the Signal-Reality match.
  - If Signal flips, Janitor closes the current position first, then the Evaluator takes the new trade.
  - If square-off fails, it retries every 15 seconds and notifies Telegram.
- **Bracket Orders**: Server-side SL (-40%) and TP (+100%) are placed immediately after entry.
- **Zombie Lock Recovery**: If the exchange is empty but memory says "active", the lock is automatically released.

## 4. Operational Guidelines
- **Telegram Alerts**: 
  - Notifies on trade entry/exit.
  - Notifies on persistent square-off failures (manual intervention requested).
  - 30-minute Pulse heartbeats.
- **Mode**: Supports PAPER and LIVE modes via Dashboard.
- **API Persistence**: Uses Delta Exchange India (api.india.delta.exchange) with IPv4 forcing.
