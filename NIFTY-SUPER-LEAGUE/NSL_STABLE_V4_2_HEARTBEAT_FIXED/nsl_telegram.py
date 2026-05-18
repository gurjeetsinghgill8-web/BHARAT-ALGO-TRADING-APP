"""
nsl_telegram.py — NIFTY SUPER LEAGUE | LEGO 8: Telegram
=========================================================
All Telegram messaging for the engine.
Pre-defined templates for every event type.

REMOVED: profit target, anchor references.
UPDATED: startup shows 9:20–3:10 window, no TP line.
"""

import requests
import nsl_db as db
import nsl_config as cfg


def send_msg(text: str) -> bool:
    """Send a message to the configured Telegram chat."""
    token   = db.get("telegram_bot_token")
    chat_id = db.get("telegram_chat_id")
    if not token or not chat_id:
        return False
    try:
        resp = requests.post(
            cfg.TELEGRAM_API.format(token=token),
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=8,
            proxies=db.get_proxy(),
        )
        return resp.status_code == 200
    except Exception:
        return False


# ─── Message Templates ────────────────────────────────────────

def msg_startup(st_period: int, st_multiplier: float, lots: int) -> str:
    return (
        f"🏆 <b>NIFTY SUPER LEAGUE v4 — STARTED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📐 SuperTrend : {st_period}/{st_multiplier} (5-min candles)\n"
        f"📦 Lots       : {lots} lot × 65 = {lots * 65} units\n"
        f"🔄 Exit Rule  : Hold until SuperTrend flips\n"
        f"⏰ Window     : 09:20 – 15:10 IST\n"
        f"🛡️ Lot Guard  : Max 1 lot enforced every candle\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Engine LIVE | SuperTrend is the ONLY signal 🍀"
    )


def msg_entry(direction: str, strike: float, opt_type: str, premium: float,
              expiry: str, lots: int, lot_size: int,
              ltp: float, st_value: float, st_dir: str) -> str:
    arrow   = "↑" if direction == "CALL" else "↓"
    sl_pct  = float(db.get("stop_loss_pct", "0") or "0")
    sl_line = (
        f"🛑 Stop Loss : ₹{premium * (1 - sl_pct / 100):.2f} (-{sl_pct:.0f}%)"
        if sl_pct > 0
        else "🛑 Stop Loss : Disabled (manual cut from dashboard)"
    )
    return (
        f"🟢 <b>TRADE ENTRY — {direction} {arrow}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Signal     : BUY {opt_type}\n"
        f"Strike     : ₹{strike:,.0f} {opt_type}\n"
        f"Premium    : ₹{premium:.2f}\n"
        f"Expiry     : {expiry}\n"
        f"Qty        : {lots} × {lot_size} = {lots * lot_size} units\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Nifty LTP  : ₹{ltp:,.2f}\n"
        f"SuperTrend : ₹{st_value:,.2f} ({st_dir})\n"
        f"🔄 Hold    : Until SuperTrend flips\n"
        f"{sl_line}"
    )


def msg_exit_flip(old_direction: str, new_direction: str,
                  premium_entry: float, premium_exit: float, pnl_pct: float) -> str:
    emoji = "📉" if pnl_pct < 0 else "📈"
    return (
        f"🔄 <b>SUPERTREND FLIP — EXITING ALL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Was          : {old_direction}\n"
        f"Now          : {new_direction}\n"
        f"Entry Premium: ₹{premium_entry:.2f}\n"
        f"Exit Premium : ₹{premium_exit:.2f}\n"
        f"{emoji} P&L %     : {pnl_pct:+.1f}%\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Squaring off ALL & re-entering on new signal..."
    )


def msg_exit_sl(premium_entry: float, premium_exit: float, pnl_pct: float,
                lots: int, lot_size: int) -> str:
    pnl_abs = (premium_exit - premium_entry) * lots * lot_size
    return (
        f"🛑 <b>STOP LOSS HIT — SQUARE OFF</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Entry Premium : ₹{premium_entry:.2f}\n"
        f"Exit Premium  : ₹{premium_exit:.2f}\n"
        f"Loss          : {pnl_pct:.1f}%\n"
        f"Approx P&L    : ₹{pnl_abs:,.0f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Waiting for next SuperTrend signal to re-enter."
    )


def msg_exit_market_close(premium_entry: float, premium_exit: float, pnl_pct: float) -> str:
    return (
        f"🕒 <b>3:10 PM — FORCE SQUARE OFF</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Entry  : ₹{premium_entry:.2f}\n"
        f"Exit   : ₹{premium_exit:.2f}\n"
        f"P&L %  : {pnl_pct:+.1f}%\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"All positions closed for the day. See you tomorrow! 🌙"
    )


def msg_heartbeat(ltp: float, st_value: float, st_direction: str,
                  signal: str, active_symbol: str, pnl_pct: float,
                  entry_premium: float, current_opt_ltp: float,
                  st_health: str) -> str:
    dir_arrow   = "↑ BULLISH" if st_direction == "BULLISH" else "↓ BEARISH" if st_direction == "BEARISH" else "— NONE"
    pos_str     = f"HOLDING {active_symbol}" if active_symbol != "NONE" else "FLAT (No Position)"
    health_icon = "✅" if st_health == "OK" else "⚠️" if st_health == "STALE" else "❌"
    return (
        f"📊 <b>NIFTY SUPER LEAGUE — PULSE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Nifty LTP  : ₹{ltp:,.2f}\n"
        f"SuperTrend : ₹{st_value:,.2f} {dir_arrow}\n"
        f"ST Health  : {health_icon} {st_health}\n"
        f"Signal     : {signal}\n"
        f"Trade      : {pos_str}\n"
        f"Entry Prem : ₹{entry_premium:.2f}\n"
        f"Curr Prem  : ₹{current_opt_ltp:.2f}\n"
        f"Live P&L % : {pnl_pct:+.1f}%"
    )


def msg_st_stale_alert(minutes_ago: float) -> str:
    return (
        f"⚠️ <b>SUPERTREND HEALTH WARNING</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Last Update : {minutes_ago:.0f} minutes ago\n"
        f"Status      : STALE — Data feed may be stuck\n"
        f"Action      : Check engine logs. Candle API may be failing.\n"
        f"Trading     : PAUSED until ST recovers."
    )


def msg_lot_breach(total_lots: int, positions: int) -> str:
    return (
        f"🚨 <b>LOT INTEGRITY BREACH FIXED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Found : {total_lots} lots ({positions} positions)\n"
        f"Max   : 1 lot allowed\n"
        f"Action: ALL excess positions closed automatically.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Safety guard fired. Check what caused multi-lot entry."
    )


def msg_error(context: str, detail: str) -> str:
    return (
        f"❌ <b>NSL ENGINE ERROR</b>\n"
        f"Context : {context}\n"
        f"Detail  : {detail[:200]}"
    )
