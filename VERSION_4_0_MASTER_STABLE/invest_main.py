"""
invest_main.py — BHARAT ALGOVERSE v3.0 | RS LegoMaster Scheduler
=================================================================
Daily scheduler that sends:
  • 8:00 AM IST → Full Daily RS Report (Mon–Fri)
  • Sunday 7:00 PM → Weekly Summary
  • 1st of month 8:00 AM → Monthly Overview (same as daily + monthly note)

Completely isolated from crypto + nifty modules.
Start with:  python invest_main.py
"""

import time
import sys
import socket
import traceback
from datetime import datetime
import pytz
import db
import invest_report
from utils import log_terminal, send_telegram_msg

IST = pytz.timezone("Asia/Kolkata")

# Singleton lock — will not conflict with crypto(47200) or nifty(47201)
LOCK_PORT = 47202


def _acquire_lock():
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(('127.0.0.1', LOCK_PORT))
        return lock
    except socket.error:
        print("🚨 INVEST BOT ALREADY RUNNING. EXITING.")
        sys.exit(1)


def _now_ist():
    return datetime.now(IST)


def _should_send_daily(now: datetime, last_sent_date: str) -> bool:
    """True if it's Mon-Fri, 8:00-8:05 AM IST, and not already sent today."""
    if now.weekday() >= 5:           # Skip Sat/Sun
        return False
    if not (8 <= now.hour < 9 and now.minute < 5):
        return False
    today_str = now.strftime("%Y-%m-%d")
    return last_sent_date != today_str


def _should_send_weekly(now: datetime, last_weekly: str) -> bool:
    """True if it's Sunday 7:00-7:05 PM IST and not sent this week."""
    if now.weekday() != 6:           # Only Sunday
        return False
    if not (19 <= now.hour < 20 and now.minute < 5):
        return False
    this_week = now.strftime("%Y-W%W")
    return last_weekly != this_week


def main():
    lock = _acquire_lock()

    print("=" * 60)
    print("   💹 BHARAT ALGOVERSE v3.0 — RS LEGOMASTER STARTED   ")
    print("=" * 60)
    print("  ✅ Daily Report: 8:00 AM IST (Mon-Fri)")
    print("  ✅ Weekly Report: Sunday 7:00 PM IST")
    print("  ✅ RS Period: 55 days (primary)")
    print("  ✅ Mode: Analysis Only — NO auto-trading")
    print("=" * 60)

    # Load secrets (Telegram token needed)
    db.load_secrets()

    # Initialize defaults
    defaults = {
        "invest_rs_period":       "55",
        "invest_top_sectors_n":   "5",
        "invest_top_stocks_n":    "3",
        "invest_algo_running":    "ON",
        "invest_last_daily_date": "",
        "invest_last_weekly_wk":  "",
    }
    for k, v in defaults.items():
        if not db.get_param(k):
            db.set_param(k, v)

    send_telegram_msg(
        "💹 *RS LEGOMASTER STARTED*\n"
        "Daily 8AM report active (Mon-Fri)\n"
        "Weekly summary every Sunday 7PM\n"
        "Mode: Research Only"
    )

    loop_sleep = 60  # check every 60 seconds

    while True:
        try:
            if db.get_param("invest_algo_running", "ON") == "OFF":
                print("[INVEST] Bot paused by user. Sleeping 5min...")
                time.sleep(300)
                continue

            now        = _now_ist()
            last_daily = db.get_param("invest_last_daily_date", "") or ""
            last_weekly= db.get_param("invest_last_weekly_wk",  "") or ""

            # ── Daily Report (8 AM Mon-Fri) ──────────────────
            if _should_send_daily(now, last_daily):
                log_terminal("[INVEST] Sending daily report...", "INFO")
                success = invest_report.send_daily_rs_report("DAILY")
                if success:
                    db.set_param("invest_last_daily_date", now.strftime("%Y-%m-%d"))

            # ── Weekly Report (Sunday 7 PM) ───────────────────
            elif _should_send_weekly(now, last_weekly):
                log_terminal("[INVEST] Sending weekly report...", "INFO")
                success = invest_report.send_daily_rs_report("WEEKLY")
                if success:
                    db.set_param("invest_last_weekly_wk", now.strftime("%Y-W%W"))

            # ── Heartbeat ─────────────────────────────────────
            else:
                next_report = "Tomorrow 8:00 AM" if now.weekday() < 5 else "Monday 8:00 AM"
                if now.second < 10 and now.minute % 30 == 0:
                    print(f"[INVEST] Alive | {now.strftime('%H:%M')} IST | Next: {next_report}")

            time.sleep(loop_sleep)

        except KeyboardInterrupt:
            log_terminal("[INVEST] Scheduler stopped by user.", "INFO")
            break
        except Exception as e:
            print(f"[INVEST LOOP ERROR] {e}")
            traceback.print_exc()
            time.sleep(60)

    lock.close()


if __name__ == "__main__":
    main()
