"""
nsl_engine.py — NIFTY SUPER LEAGUE | LEGO 7: Main Engine Loop
==============================================================
STRICT STATE MACHINE — SuperTrend Edition v4.0

RULES (non-negotiable):
  1. Exchange-first: ALWAYS verify positions before any action
  2. ONE lot maximum: LOT GUARD runs every new-candle cycle
  3. SuperTrend only: no anchor, no manual signal override
  4. Use PREVIOUS CLOSED candle only (forming candle dropped in nsl_data.py)
  5. FLIP = close ALL positions → verify flat → enter new
  6. First-run guard: skip first cycle after engine start/restart
  7. No profit target: hold until SuperTrend flips
  8. Stop Loss: disabled by default, dashboard-only manual cut
  9. Market: 9:20 AM start | 3:10 PM force close (all intraday)
 10. On non-new-candle cycles: refresh BOTH Nifty LTP and option LTP
"""

import time
import socket
import sys
import traceback

import nsl_db as db
import nsl_config as cfg
import nsl_utils as utils
import nsl_data as data
import nsl_supertrend as st_mod
import nsl_executor as executor
import nsl_telegram as tg


# ─────────────────────────────────────────────────────────────
# Singleton lock (prevents double-start)
# ─────────────────────────────────────────────────────────────
def _acquire_lock():
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", cfg.LOCK_PORT))
        return lock
    except OSError:
        print(f"NIFTY SUPER LEAGUE ALREADY RUNNING (port {cfg.LOCK_PORT}). Exiting.")
        sys.exit(1)


# ─────────────────────────────────────────────────────────────
# VPS-ONLY GUARD — CRITICAL RULE
# This engine MUST run on VPS (46.224.133.16) ONLY.
# Upstox IP whitelist will BLOCK all orders from any other IP.
# ─────────────────────────────────────────────────────────────
VPS_IP = "46.224.133.16"

def _check_vps_only():
    """Block execution if not running on the whitelisted VPS IP."""
    try:
        import requests as _req
        my_ip = _req.get("https://ifconfig.me", timeout=6).text.strip()
    except Exception:
        try:
            import urllib.request
            my_ip = urllib.request.urlopen("https://ifconfig.me", timeout=6).read().decode().strip()
        except Exception:
            print("[VPS GUARD] Could not determine public IP — allowing startup (check manually).")
            return

    if my_ip != VPS_IP:
        print("=" * 62)
        print("  BLOCKED — LAPTOP/LOCAL EXECUTION DETECTED")
        print(f"  Your IP : {my_ip}")
        print(f"  VPS IP  : {VPS_IP}  (Upstox whitelisted)")
        print()
        print("  This engine MUST run on the VPS only.")
        print("  Run it at: ssh root@46.224.133.16")
        print("  Dashboard: http://46.224.133.16:8502")
        print("=" * 62)
        sys.exit(1)
    print(f"[VPS GUARD] IP confirmed: {my_ip} — OK to trade.")



# ─────────────────────────────────────────────────────────────
# First-run guard (skip first cycle after any start/restart)
# ─────────────────────────────────────────────────────────────
_first_run = True


# ─────────────────────────────────────────────────────────────
# Self-Healing Agent v4.1
# ─────────────────────────────────────────────────────────────
_stale_ltp_cycles = 0

def _self_healing_check() -> bool:
    """
    Runs safety checks every cycle. Auto-fixes what it can.
    Returns True  = all OK, proceed with trading.
    Returns False = problem detected + handled, skip this cycle.
    """
    global _stale_ltp_cycles

    # ── Check 1: LTP unavailable while holding a position ────
    if db.get("trade_active") == "YES":
        if db.get("ltp_fetch_failed", "NO") == "YES":
            _stale_ltp_cycles += 1
            utils.log(
                f"SELF-HEAL: LTP=0 for {_stale_ltp_cycles} consecutive cycle(s).",
                "ALERT"
            )
            if _stale_ltp_cycles >= 2:
                utils.log(
                    "SELF-HEAL: LTP unavailable 2 cycles — auto-closing position for safety.",
                    "ALERT"
                )
                tg.send_msg(
                    f"🚨 <b>AUTO-HEAL: Position Closed</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Option LTP fetch failed for {_stale_ltp_cycles} candle cycles.\n"
                    f"Position closed for safety.\n"
                    f"Engine is now FLAT — will re-enter on next valid signal."
                )
                executor.square_off_all_positions()
                _stale_ltp_cycles = 0
                db.set("ltp_fetch_failed", "NO")
                return False
        else:
            _stale_ltp_cycles = 0
    else:
        _stale_ltp_cycles = 0
        db.set("ltp_fetch_failed", "NO")

    return True


# ─────────────────────────────────────────────────────────────
# New-day detection
# ─────────────────────────────────────────────────────────────
_last_run_date = None

def _check_new_day() -> bool:
    global _last_run_date
    today = utils.ist_today()
    if today != _last_run_date:
        _last_run_date = today
        return True
    return False


# ─────────────────────────────────────────────────────────────
# Stop Loss check (disabled by default — dashboard only)
# ─────────────────────────────────────────────────────────────
def _check_stop_loss() -> bool:
    """
    Returns True if SL hit and position closed.
    SL is disabled when stop_loss_pct = 0.
    """
    sl_pct = float(db.get("stop_loss_pct", str(cfg.DEFAULT_STOP_LOSS_PCT)) or cfg.DEFAULT_STOP_LOSS_PCT)
    if sl_pct <= 0:
        return False  # SL disabled

    entry_premium = float(db.get("entry_premium", "0") or "0")
    current_ltp   = float(db.get("current_option_ltp", "0") or "0")
    if entry_premium <= 0 or current_ltp <= 0:
        return False

    loss_pct = ((current_ltp - entry_premium) / entry_premium) * 100

    utils.log(
        f"SL Check: Entry ₹{entry_premium:.2f} | Now ₹{current_ltp:.2f} | "
        f"Loss: {loss_pct:.1f}% | SL: -{sl_pct:.0f}%",
        "INFO"
    )

    if loss_pct <= -sl_pct:
        utils.log(f"STOP LOSS HIT: {loss_pct:.1f}%! Closing ALL...", "ALERT")
        lots     = int(db.get("lots",     str(cfg.DEFAULT_LOTS))     or cfg.DEFAULT_LOTS)
        lot_size = int(db.get("lot_size", str(cfg.DEFAULT_LOT_SIZE)) or cfg.DEFAULT_LOT_SIZE)
        tg.send_msg(tg.msg_exit_sl(entry_premium, current_ltp, loss_pct, lots, lot_size))
        executor.square_off_all_positions()
        return True

    return False


# ─────────────────────────────────────────────────────────────
# MAIN CYCLE
# ─────────────────────────────────────────────────────────────
def run_one_cycle() -> None:
    global _first_run

    # ── 0. Market closed? ────────────────────────────────────
    if not utils.is_market_open():
        return

    # ── 1. Engine paused / auto-blocked from dashboard? ──────
    algo_state = db.get("algo_running", "ON")
    if algo_state == "OFF":
        utils.log("Engine paused from dashboard.", "WAIT")
        return
    if algo_state == "BLOCKED":
        utils.log("Engine AUTO-BLOCKED. Check dashboard/Telegram for reason.", "ALERT")
        return

    # ── 2. First-run guard ───────────────────────────────────
    if _first_run:
        utils.log(
            "FIRST RUN GUARD: Skipping first cycle after start. "
            "Will trade from next candle.",
            "GUARD"
        )
        _first_run = False
        return

    # ── 3. Force close at 3:10 PM ────────────────────────────
    if utils.is_squareoff_time():
        positions = executor.get_all_nse_fo_positions()
        if positions:
            entry_prem = float(db.get("entry_premium", "0") or "0")
            active_sym = db.get("active_symbol", "NONE")
            opt_ltp    = data.get_option_ltp(active_sym) if active_sym != "NONE" else 0.0
            pnl_pct    = ((opt_ltp - entry_prem) / entry_prem * 100) if entry_prem > 0 else 0.0
            utils.log("3:10 PM FORCE CLOSE — squaring off ALL positions!", "ALERT")
            tg.send_msg(tg.msg_exit_market_close(entry_prem, opt_ltp, pnl_pct))
            executor.square_off_all_positions()
        return

    # ── 4. Fetch Nifty Spot LTP (always live) ────────────────
    ltp = data.get_nifty_spot_ltp()
    db.set("current_ltp", str(ltp))

    # ── 5. Get closed candles for SuperTrend ─────────────────
    closed_candles = data.get_candles_for_supertrend()
    if not closed_candles:
        utils.log("Not enough closed candles. Waiting.", "WAIT")
        return

    # ── 6. Candle guard — only process each new candle once ──
    prev_candle = closed_candles[-1]

    if not data.is_new_candle(prev_candle):
        # Same candle — refresh LTPs only (no signal logic)
        utils.log(
            f"Same candle ({prev_candle['timestamp']}) — already processed. Refreshing LTPs.",
            "WAIT"
        )
        if db.get("trade_active") == "YES":
            active_sym = db.get("active_symbol", "NONE")
            if active_sym != "NONE":
                opt_ltp = data.get_option_ltp(active_sym)
                if opt_ltp > 0:
                    entry_prem = float(db.get("entry_premium", "0") or "0")
                    pnl = ((opt_ltp - entry_prem) / entry_prem * 100) if entry_prem > 0 else 0.0
                    db.set("unrealized_pnl_pct",  str(round(pnl, 2)))
                    db.set("current_option_ltp",  str(opt_ltp))
        return

    # ── 7. Compute SuperTrend on closed candles ───────────────
    st_result = st_mod.compute_and_store(closed_candles)
    if st_result is None:
        utils.log("SuperTrend returned no result. Skipping cycle.", "WAIT")
        data.record_candle_time(prev_candle)
        return

    new_st_direction = st_result["direction"]           # 'BULLISH' or 'BEARISH'
    new_signal       = st_mod.direction_to_signal(new_st_direction)  # 'CALL' or 'PUT'

    # ── 8. ST Health watchdog ────────────────────────────────
    st_health = st_mod.check_health()
    if st_health == "STALE":
        utils.log("ST WATCHDOG: SuperTrend is STALE. Pausing cycle.", "ALERT")
        tg.send_msg(tg.msg_st_stale_alert(15))
        data.record_candle_time(prev_candle)
        return

    # ── 9. LOT INTEGRITY GUARD ────────────────────────────────
    integrity_ok = executor.enforce_lot_integrity()
    if not integrity_ok:
        utils.log("LOT GUARD: Integrity violation fixed. Skipping this cycle.", "GUARD")
        data.record_candle_time(prev_candle)
        return

    # ── 9b. SELF-HEALING CHECK (v4.1) ────────────────────────
    heal_ok = _self_healing_check()
    if not heal_ok:
        utils.log("SELF-HEAL: Action taken this cycle — skipping trade logic.", "ALERT")
        data.record_candle_time(prev_candle)
        return

    # ── 10. Update live option P&L ────────────────────────────
    trade_active = db.get("trade_active") == "YES"
    current_dir  = db.get("active_option_type", "NONE")

    if trade_active:
        active_sym = db.get("active_symbol", "NONE")
        if active_sym != "NONE":
            opt_ltp = data.get_option_ltp(active_sym)
            if opt_ltp > 0:
                entry_prem = float(db.get("entry_premium", "0") or "0")
                pnl = ((opt_ltp - entry_prem) / entry_prem * 100) if entry_prem > 0 else 0.0
                db.set("unrealized_pnl_pct",  str(round(pnl, 2)))
                db.set("current_option_ltp",  str(opt_ltp))
    else:
        db.set("unrealized_pnl_pct", "0")
        db.set("current_option_ltp", "0")

    # ── 11. Update signal in DB ───────────────────────────────
    old_signal = db.get("signal", "NONE")
    db.set("last_signal", old_signal)
    db.set("signal",      new_signal)

    utils.log(
        f"SuperTrend: {new_st_direction} | Signal: {new_signal} | "
        f"ST Line=₹{st_result['st_value']:,.2f} | "
        f"Candle Close=₹{prev_candle['close']:,.2f}",
        "INFO"
    )

    # ── 12. STATE MACHINE ─────────────────────────────────────

    if not trade_active:
        # ── FLAT → Enter on signal ────────────────────────
        utils.log(f"FLAT. SuperTrend={new_st_direction}. Entering {new_signal}...", "TRADE")
        entered = executor.execute_entry(new_signal)
        if entered:
            # v4.1: Verify entry actually landed on exchange (10s settlement)
            time.sleep(10)
            pos_check = executor.get_all_nse_fo_positions()
            if not pos_check:
                utils.log("ENTRY not confirmed on exchange. Retrying once...", "ALERT")
                tg.send_msg(
                    f"⚠️ <b>Entry Not Confirmed!</b>\n"
                    f"Order placed but not found on exchange after 10s.\n"
                    f"Retrying {new_signal} entry once..."
                )
                executor._clear_trade_db()
                time.sleep(5)
                executor.execute_entry(new_signal)
            else:
                utils.log(f"ENTRY confirmed: {len(pos_check)} position(s) on exchange.", "OK")

    else:
        # ── HOLDING a position ────────────────────────────

        # Optional SL check (only fires if SL is configured > 0)
        sl_triggered = _check_stop_loss()
        if sl_triggered:
            data.record_candle_time(prev_candle)
            return

        # SuperTrend flip check — compare CALL/PUT to CALL/PUT (NOT direction to option type)
        flipped = st_mod.detect_flip(new_signal, current_dir)

        if not flipped:
            # Same direction — HOLD
            entry_prem = float(db.get("entry_premium", "0") or "0")
            opt_ltp    = float(db.get("current_option_ltp", "0") or "0")
            pnl_pct    = float(db.get("unrealized_pnl_pct", "0") or "0")
            utils.log(
                f"Holding {current_dir}. ST={new_st_direction}. "
                f"P&L: {pnl_pct:+.1f}%",
                "INFO"
            )

        else:
            # ── FLIP DETECTED — exit ALL then re-enter ────
            utils.log(
                f"FLIP: {current_dir} → {new_signal}. "
                f"Closing ALL positions first...",
                "ALERT"
            )

            entry_prem_f = float(db.get("entry_premium", "0") or "0")
            opt_ltp_f    = float(db.get("current_option_ltp", "0") or "0")
            gain_pct     = ((opt_ltp_f - entry_prem_f) / entry_prem_f * 100) if entry_prem_f > 0 else 0.0
            tg.send_msg(tg.msg_exit_flip(current_dir, new_signal, entry_prem_f, opt_ltp_f, gain_pct))

            exit_ok = executor.square_off_all_positions()

            if exit_ok:
                utils.log("All positions closed. Waiting 15s for exchange to settle...", "TRADE")
                time.sleep(15)

                # Verify exchange is flat before re-entering
                still_open = executor.get_all_nse_fo_positions()
                if still_open:
                    utils.log(
                        f"Exchange still shows {len(still_open)} open position(s). "
                        f"Waiting next candle to re-enter.",
                        "WAIT"
                    )
                else:
                    utils.log(f"Exchange confirmed FLAT. Entering {new_signal}...", "TRADE")
                    entered = executor.execute_entry(new_signal)
                    if entered:
                        # v4.1: Verify flip re-entry landed on exchange
                        time.sleep(10)
                        pos_check = executor.get_all_nse_fo_positions()
                        if not pos_check:
                            utils.log(
                                "FLIP ENTRY not confirmed on exchange. Retrying once...",
                                "ALERT"
                            )
                            tg.send_msg(
                                f"⚠️ <b>Flip Entry Not Confirmed!</b>\n"
                                f"Flip re-entry not found on exchange after 10s.\n"
                                f"Retrying {new_signal}..."
                            )
                            executor._clear_trade_db()
                            time.sleep(5)
                            executor.execute_entry(new_signal)
                        else:
                            utils.log(
                                f"FLIP ENTRY confirmed: {len(pos_check)} position(s) on exchange.",
                                "OK"
                            )
            else:
                utils.log("Exit order failed! Not entering new trade. Will retry next candle.", "ERROR")

    data.record_candle_time(prev_candle)


# ─────────────────────────────────────────────────────────────
# Startup sync — exchange is always the truth
# ─────────────────────────────────────────────────────────────
def _startup_sync():
    utils.log("Startup: syncing with exchange...", "INFO")
    try:
        positions = executor.get_all_nse_fo_positions()
        if positions:
            lot_size   = int(db.get("lot_size", str(cfg.DEFAULT_LOT_SIZE)) or cfg.DEFAULT_LOT_SIZE)
            total_lots = sum(
                abs(int(float(p.get("quantity", 0)))) // lot_size
                for p in positions
            )
            pos  = positions[0]
            sym  = pos.get("instrument_token", "NONE")
            name = pos.get("trading_symbol", "")
            dir_ = "CALL" if "CE" in name else "PUT" if "PE" in name else "NONE"

            utils.log(
                f"Startup sync: {total_lots} lot(s), {len(positions)} position(s). "
                f"Symbol: {sym} ({dir_}). Syncing DB.",
                "OK"
            )

            if total_lots > cfg.MAX_ALLOWED_LOTS:
                utils.log(
                    f"Startup sync: EXCESS LOTS ({total_lots}) — closing ALL before starting!",
                    "ALERT"
                )
                tg.send_msg(
                    f"🚨 <b>STARTUP: EXCESS LOTS!</b>\n"
                    f"Found {total_lots} lots. Closing ALL before engine starts."
                )
                executor.square_off_all_positions()
                utils.log("Startup: excess lots cleared. Starting fresh.", "OK")
            else:
                db.set("trade_active",       "YES")
                db.set("active_symbol",      sym)
                db.set("active_option_type", dir_)
                if not db.get("entry_time", ""):
                    db.set("entry_time", utils.fmt_time())
                utils.log(f"Startup sync: found live {dir_} position {sym}. DB synced.", "OK")
        else:
            executor._clear_trade_db()
            utils.log("Startup sync: exchange flat. Starting fresh.", "OK")
    except Exception as e:
        utils.log(f"Startup sync failed: {e}", "ERROR")


# ─────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────
def main():
    lock = _acquire_lock()

    print("=" * 62)
    print("  NIFTY SUPER LEAGUE  v4.0  —  SUPERTREND EDITION  ")
    print("=" * 62)
    print("  Rule 1: Exchange-first — verify before every entry")
    print("  Rule 2: ONE lot max — lot guard every candle")
    print("  Rule 3: Exit ALL on flip — verify flat first")
    print("  Rule 4: Previous closed candle only — never forming")
    print("  Rule 5: SuperTrend is the ONLY signal")
    print("  Rule 6: Hold until flip — no profit target")
    print("  Rule 7: 9:20 AM start | 3:10 PM force close")
    print("=" * 62)

    db.init_defaults()

    if not db.is_setup_complete():
        utils.log("Credentials not set. Open dashboard to configure.", "ALERT")
        while not db.is_setup_complete():
            time.sleep(15)
        utils.log("Credentials found! Starting engine...", "OK")

    _startup_sync()

    st_period     = int(db.get("st_period",     str(cfg.DEFAULT_ST_PERIOD))     or cfg.DEFAULT_ST_PERIOD)
    st_multiplier = float(db.get("st_multiplier", str(cfg.DEFAULT_ST_MULTIPLIER)) or cfg.DEFAULT_ST_MULTIPLIER)
    lots          = int(db.get("lots", str(cfg.DEFAULT_LOTS)) or cfg.DEFAULT_LOTS)
    tg.send_msg(tg.msg_startup(st_period, st_multiplier, lots))

    last_heartbeat = 0

    while True:
        try:
            if _check_new_day():
                utils.log(
                    "New trading day. Resetting candle guard and ST health.",
                    "INFO"
                )
                db.set("last_candle_time", "")
                db.set("st_health",        "OK")
                db.set("st_last_update",   "")

            run_one_cycle()

            # Heartbeat every 10 minutes — v4.1: ONLY when engine is actively ON
            if utils.is_market_open() and db.get("algo_running", "ON") == "ON":
                now_ts = time.time()
                if now_ts - last_heartbeat >= 600:
                    ltp       = float(db.get("current_ltp",        "0") or "0")
                    st_val    = float(db.get("st_value",            "0") or "0")
                    st_dir    = db.get("st_direction",  "NONE")
                    sig       = db.get("signal",        "NONE")
                    active_sym= db.get("active_symbol", "NONE")
                    entry_prem= float(db.get("entry_premium",       "0") or "0")
                    opt_ltp   = float(db.get("current_option_ltp",  "0") or "0")
                    pnl_pct   = float(db.get("unrealized_pnl_pct",  "0") or "0")
                    st_health = db.get("st_health", "OK")
                    tg.send_msg(tg.msg_heartbeat(
                        ltp, st_val, st_dir, sig,
                        active_sym, pnl_pct, entry_prem, opt_ltp, st_health
                    ))
                    last_heartbeat = now_ts

            sleep_secs = utils.seconds_to_next_5min_candle()
            utils.log(f"Sleeping {sleep_secs}s until next candle...", "WAIT")
            time.sleep(sleep_secs)

        except KeyboardInterrupt:
            utils.log("Engine stopped by user.", "INFO")
            break
        except Exception as e:
            utils.log(f"MAIN LOOP ERROR: {e}", "ERROR")
            traceback.print_exc()
            tg.send_msg(tg.msg_error("MAIN LOOP", str(e)[:200]))
            time.sleep(30)

    lock.close()


if __name__ == "__main__":
    _check_vps_only()   # BLOCK if not on VPS — must be first
    main()

