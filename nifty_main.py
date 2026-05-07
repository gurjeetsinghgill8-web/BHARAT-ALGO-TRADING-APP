"""
nifty_main.py — BHARAT ALGOVERSE v3.0 | Nifty Bot Runner
=========================================================
Runs COMPLETELY SEPARATELY from the crypto (main.py) bot.
Start with:  python nifty_main.py

Key Rules:
• Only trades 9:25 AM – 3:10 PM IST, Mon–Fri
• Positional style: holds trade until signal flips or SL/TP
• Stop Loss: configurable (default 30% of premium)
• Take Profit: configurable (default 80% of premium)
• Uses its OWN DB keys (prefix: nifty_) — no crypto DB conflict
• Auto Telegram pulse every 30 min during market hours
• Singleton lock on port 47201 (crypto uses 47200)
"""

import time
import sys
import socket
import traceback
import db
from utils import log_terminal, send_telegram_msg
import nifty_logic
import nifty_executor


# ============================================================
# SINGLETON LOCK (won't conflict with crypto bot port 47200)
# ============================================================
def _acquire_lock():
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(('127.0.0.1', 47201))
        return lock
    except socket.error:
        print("🚨 NIFTY BOT ALREADY RUNNING. EXITING.")
        sys.exit(1)


# ============================================================
# SL / TP MONITOR (premium-based, not exchange PnL)
# ============================================================
def check_nifty_sl_tp():
    """
    Checks if current position has hit SL or TP based on LTP vs entry premium.
    Runs only in LIVE mode.
    """
    if db.get_param('nifty_trade_active', 'NO') != 'YES':
        return
    is_live = db.get_param('nifty_trade_mode', 'PAPER') == 'LIVE'
    entry_prem = float(db.get_param('nifty_entry_premium', '0') or '0')
    if entry_prem <= 0: return

    sl_pct = float(db.get_param('nifty_sl_percent', '30') or '30')
    tp_pct = float(db.get_param('nifty_tp_percent', '80') or '80')

    if is_live:
        positions = nifty_executor.get_nifty_positions()
        if not positions:
            db.set_param('nifty_trade_active', 'NO')
            db.set_param('nifty_active_symbol', 'NONE')
            return
        
        # In LIVE mode, we trust the exchange LTP
        for p in positions:
            ltp = float(p.get('last_price', 0) or p.get('ltp', 0))
            if ltp <= 0: continue
            pnl_pct = ((ltp - entry_prem) / entry_prem) * 100
            db.set_param('nifty_unrealized_pnl', str(pnl_pct))
            
            if pnl_pct <= -sl_pct:
                log_terminal(f"🚨 NIFTY STOP LOSS HIT: {pnl_pct:.1f}% | Exiting...", "ALERT")
                send_telegram_msg(f"🔴 NIFTY SL TRIGGERED | Loss: {pnl_pct:.1f}%")
                nifty_executor.square_off_nifty_all()
            elif pnl_pct >= tp_pct:
                log_terminal(f"💰 NIFTY TAKE PROFIT HIT: {pnl_pct:.1f}% | Booking...", "TRADE")
                send_telegram_msg(f"✅ NIFTY TP HIT | Profit: {pnl_pct:.1f}% 🎯")
                nifty_executor.square_off_nifty_all()
    else:
        # PAPER MODE: Fetch LTP for the tracked virtual key
        v_key = db.get_param('nifty_active_key', '')
        if not v_key: return
        
        ltp = nifty_executor.get_nifty_ltp(v_key)
        if ltp <= 0: return
        
        pnl_pct = ((ltp - entry_prem) / entry_prem) * 100
        db.set_param('nifty_unrealized_pnl', str(pnl_pct))
        
        # In paper mode, we still check for SL/TP to auto-exit
        if pnl_pct <= -sl_pct or pnl_pct >= tp_pct:
            log_terminal(f"[NIFTY] PAPER {'SL' if pnl_pct < 0 else 'TP'} HIT: {pnl_pct:.1f}%", "TRADE")
            db.set_param('nifty_trade_active', 'NO')
            db.set_param('nifty_active_symbol', 'NONE')
            send_telegram_msg(f"📝 NIFTY PAPER TRADE CLOSED | PnL: {pnl_pct:.1f}%")


# ============================================================
# MAIN EVALUATOR
# ============================================================
def run_nifty_sar():
    """
    Core SAR loop: evaluate signal → entry or hold.
    Only runs if market is open AND nifty bot is enabled.
    """
    if db.get_param('nifty_algo_running', 'OFF') == 'OFF':
        return

    if not nifty_logic.is_market_open():
        return

    symbol    = db.get_param('nifty_symbol', '^NSEI') or '^NSEI'
    timeframe = db.get_param('nifty_timeframe', '15m') or '15m'
    signal    = nifty_logic.get_nifty_signal(symbol=symbol, timeframe=timeframe)
    db.set_param('nifty_signal', signal)

    is_active  = db.get_param('nifty_trade_active', 'NO') == 'YES'
    last_dir   = db.get_param('nifty_last_direction', 'NONE') or 'NONE'

    if not is_active:
        # No open position → enter if signal is clear
        if signal in ['BUY', 'SELL']:
            log_terminal(f"[NIFTY] 🎯 SIGNAL: {signal}. Entering positional trade.", "TRADE")
            nifty_executor.execute_nifty_trade(signal)

    else:
        # Position open → check for signal flip (SAR)
        if signal == 'BUY' and last_dir == 'SELL':
            log_terminal("[NIFTY] 🔄 SAR FLIP: SELL→BUY. Exiting PUT, entering CALL.", "TRADE")
            nifty_executor.square_off_nifty_all()
            time.sleep(2)
            nifty_executor.execute_nifty_trade('BUY')

        elif signal == 'SELL' and last_dir == 'BUY':
            log_terminal("[NIFTY] 🔄 SAR FLIP: BUY→SELL. Exiting CALL, entering PUT.", "TRADE")
            nifty_executor.square_off_nifty_all()
            time.sleep(2)
            nifty_executor.execute_nifty_trade('SELL')

        elif signal == 'WAIT':
            log_terminal("[NIFTY] Signal WAIT during active trade. Holding.", "INFO")


# ============================================================
# MARKET CLOSE ROUTINE (3:10 PM rule)
# ============================================================
def run_market_close_routine():
    """Called once when market closes. Closes all positions."""
    if db.get_param('nifty_trade_active', 'NO') == 'YES':
        log_terminal("[NIFTY] 3:10 PM: Market closing. Squaring off all positions.", "ALERT")
        send_telegram_msg("🕒 NIFTY: Market closing. Squaring off all positions.")
        nifty_executor.square_off_nifty_all()


# ============================================================
# MAIN
# ============================================================
def main():
    lock = _acquire_lock()

    print("=" * 60)
    print("   📈 BHARAT ALGOVERSE v3.0 — NIFTY MODULE STARTED   ")
    print("=" * 60)
    print("  ✅ Market Window: 9:25 AM – 3:10 PM IST")
    print("  ✅ Strategy: Positional Options (Next-Week Expiry)")
    print("  ✅ Strike Rule: Nearest ₹120 premium")
    print("  ✅ Supertrend: Multi-TF | Multi-Setting")
    print("  ✅ SAR Flip: Auto-exit & re-enter on signal flip")
    print("=" * 60)

    # ── Load secrets (Upstox token + Telegram) ──────────────
    if not db.load_secrets():
        print("[NIFTY] WARNING: secrets.txt not found. Running in PAPER mode only.")
        db.set_param('nifty_trade_mode', 'PAPER')

    # Initialize Nifty defaults (only if not already set)
    defaults = {
        'nifty_symbol':          '^NSEI',
        'nifty_timeframe':       '15m',
        'nifty_st_period':       '10',
        'nifty_st_multiplier':   '1.5',
        'nifty_lots':            '1',
        'nifty_lot_size':        '25',
        'nifty_target_premium':  '120',
        'nifty_sl_percent':      '30',
        'nifty_tp_percent':      '80',
        'nifty_trade_mode':      'LIVE',      # ← LIVE by default
        'nifty_algo_running':    'ON',
        'nifty_expiry_weekday':  '1',         # ← 1 = Tuesday (Dr. Saab's expiry)
    }
    for k, v in defaults.items():
        if not db.get_param(k):
            db.set_param(k, v)

    send_telegram_msg(
        "📈 *NIFTY MODULE STARTED*\n"
        "Strategy: Positional | Supertrend SAR\n"
        "Window: 9:25 AM – 3:10 PM IST\n"
        "Mode: " + (db.get_param('nifty_trade_mode', 'PAPER') or 'PAPER')
    )

    last_pulse    = 0
    was_in_market = False
    loop_sleep    = 60  # 60s loop (slower than crypto — positional is patient)

    while True:
        try:
            in_market = nifty_logic.is_market_open()

            # ── Market just closed ──────────────────────────
            if was_in_market and not in_market:
                run_market_close_routine()

            was_in_market = in_market

            if in_market:
                run_nifty_sar()
                check_nifty_sl_tp()

                # Pulse every 30 min
                if time.time() - last_pulse > 1800:
                    signal = db.get_param('nifty_signal', 'WAIT') or 'WAIT'
                    active = db.get_param('nifty_active_symbol', 'NONE') or 'NONE'
                    upnl   = db.get_param('nifty_unrealized_pnl', '0') or '0'
                    send_telegram_msg(
                        f"📈 *NIFTY PULSE*\n"
                        f"Signal: {signal} | Active: {active[:30]}\n"
                        f"Live PnL: {upnl}% | TF: {db.get_param('nifty_timeframe','15m')}"
                    )
                    last_pulse = time.time()
            else:
                # Show countdown when market is closed
                countdown = nifty_logic.time_to_open_str()
                print(f"[NIFTY] Market closed. Opens in {countdown}. Sleeping...")

            time.sleep(loop_sleep)

        except KeyboardInterrupt:
            log_terminal("[NIFTY] Bot stopped by user.", "INFO")
            break
        except Exception as e:
            print(f"[NIFTY LOOP ERROR] {e}")
            traceback.print_exc()
            time.sleep(30)

    lock.close()


if __name__ == "__main__":
    main()
