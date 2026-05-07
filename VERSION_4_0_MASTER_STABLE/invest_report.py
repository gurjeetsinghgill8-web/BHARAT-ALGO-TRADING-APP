"""
invest_report.py — BHARAT ALGOVERSE v3.0 | RS LegoMaster Reporter
==================================================================
Generates Daily (8 AM), Weekly, and Monthly Telegram reports.
NO auto-trading — pure analysis delivery to Dr. Saab.

Report Sections:
  📊 Market Pulse (Nifty RSI)
  🏆 Top Sectors (RS-55 ranked)
  🎯 Top Stocks (RS-55 within sector, capped large)
  💰 Allocation % suggestion
  🔍 Emerging vs Weak Sectors (Quarter + Year)
  📚 Research Highlight (underdog alert)

DB Namespace: invest_*
"""

import db
from utils import send_telegram_msg, log_terminal
import invest_rs_engine as rs_engine
from datetime import datetime
import pytz
import json

IST = pytz.timezone("Asia/Kolkata")


# ============================================================
# FORMATTER HELPERS
# ============================================================
def _rs_bar(rs: float) -> str:
    """Visual bar indicator for RS strength."""
    if rs >= 1.30: return "🟢🟢🟢"
    if rs >= 1.15: return "🟢🟢"
    if rs >= 1.05: return "🟢"
    if rs >= 0.95: return "🟡"
    return "🔴"


def _cap_icon(cap: str) -> str:
    return {"Large": "🏦", "Mid": "🏢", "Small": "🏪"}.get(cap, "📦")


def _mode_icon(mode: str) -> str:
    return "🟢 AGGRESSIVE" if mode == "AGGRESSIVE" else "🔴 DEFENSIVE"


def _pct_str(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


# ============================================================
# DAILY TELEGRAM REPORT BUILDER
# ============================================================
def build_daily_report(scan: dict) -> str:
    """Formats the full daily RS report as Telegram-ready text."""
    pulse   = scan.get("pulse", {})
    tops    = scan.get("top_sectors", [])
    stocks  = scan.get("top_stocks", {})
    alloc   = scan.get("allocation", {})
    ew      = scan.get("emerg_weak", {})
    dt      = scan.get("scan_dt", "—")
    period  = scan.get("rs_period", 55)

    lines = []
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 *RS LEGOMASTER DAILY REPORT*")
    lines.append(f"📅 {dt}")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # ── Market Pulse ──────────────────────────────────────
    rsi  = pulse.get("rsi", 0)
    mode = pulse.get("mode", "UNKNOWN")
    nifty_close = pulse.get("close", 0)
    lines.append(f"\n📈 *MARKET PULSE*")
    lines.append(f"Nifty 50: ₹{nifty_close:,.0f}")
    lines.append(f"RSI(14):  {rsi:.1f}  →  {_mode_icon(mode)}")
    if mode == "AGGRESSIVE":
        lines.append("✅ Be invested. Ride momentum.")
    else:
        lines.append("⚠️ Nifty weak. Stay selective / raise cash.")

    # ── Top Sectors ───────────────────────────────────────
    lines.append(f"\n🏆 *TOP SECTORS — RS {period} vs Nifty*")
    if tops:
        for s in tops:
            bar  = _rs_bar(s["rs"])
            pct  = _pct_str(s["vs_nifty_pct"])
            lines.append(
                f"{s['rank']}. *{s['sector']}* {bar}\n"
                f"   RS: {s['rs']:.3f} | {pct} vs Nifty"
            )
    else:
        lines.append("No outperforming sectors today. Market weak — stay cautious.")

    # ── Top Stocks ────────────────────────────────────────
    lines.append(f"\n🎯 *TOP STOCKS TO WATCH*")
    for sec_name, sec_stocks in stocks.items():
        if not sec_stocks:
            continue
        lines.append(f"\n  📌 *{sec_name}*")
        for st in sec_stocks:
            icon = _cap_icon(st["cap"])
            pct  = _pct_str(st["vs_nifty_pct"])
            lines.append(
                f"  {icon} {st['symbol']} ({st['cap']} Cap)\n"
                f"     RS: {st['rs']:.3f} | {pct} vs Nifty"
            )

    # ── Allocation ────────────────────────────────────────
    lines.append(f"\n💰 *SUGGESTED ALLOCATION*")
    lines.append("_(Research only — NOT auto-trade advice)_")
    if alloc:
        total_check = 0
        for sec_name, data in alloc.items():
            sp = data["sector_pct"]
            lines.append(f"\n  📊 *{sec_name}* → {sp:.1f}% of portfolio")
            for st in data["stocks"]:
                icon = _cap_icon(st["cap"])
                lines.append(f"     {icon} {st['symbol']}: {st['alloc_pct']:.1f}%")
                total_check += st["alloc_pct"]
    else:
        lines.append("No allocation today — no strong sectors found.")

    # ── Cap Mix ───────────────────────────────────────────
    all_stocks_flat = [st for lst in stocks.values() for st in lst]
    large_count = sum(1 for s in all_stocks_flat if s["cap"] == "Large")
    mid_count   = sum(1 for s in all_stocks_flat if s["cap"] == "Mid")
    small_count = sum(1 for s in all_stocks_flat if s["cap"] == "Small")
    total_count = max(1, len(all_stocks_flat))
    lines.append(
        f"\n  Cap Mix: 🏦Large {large_count} | 🏢Mid {mid_count} | 🏪Small {small_count}"
        f" (of {total_count} stocks)"
    )

    # ── Emerging / Weak ───────────────────────────────────
    lines.append(f"\n🔍 *EMERGING vs WEAK SECTORS (Quarterly)*")
    emerging = ew.get("emerging_quarter", [])
    weak     = ew.get("weak_quarter", [])
    if emerging:
        lines.append("  ✅ *Emerging (Top QoQ):*")
        for e in emerging:
            lines.append(f"     {e['sector']}: {_pct_str(e['ret_90d'])}")
    if weak:
        lines.append("  ❌ *Weak (Bottom QoQ):*")
        for w in weak:
            lines.append(f"     {w['sector']}: {_pct_str(w['ret_90d'])}")

    # ── Underdog Alert ─────────────────────────────────────
    underdogs = [
        st for lst in stocks.values() for st in lst
        if st["cap"] == "Small" and st["rs"] >= 1.20
    ]
    if underdogs:
        lines.append(f"\n📚 *UNDERDOG ALERT* 🚀")
        for ud in underdogs[:3]:
            lines.append(
                f"  🏪 *{ud['symbol']}* (Small Cap, {ud['sector']})\n"
                f"     RS-{period}: {ud['rs']:.3f} | "
                f"+{ud['vs_nifty_pct']:.1f}% vs Nifty"
            )

    # ── Footer ────────────────────────────────────────────
    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ _For research only. Not investment advice._")
    lines.append("🩺 _BHARAT ALGOVERSE v3.0 | RS LegoMaster_")
    lines.append(f"🔁 _Next report: Tomorrow 8:00 AM IST_")

    return "\n".join(lines)


# ============================================================
# WEEKLY SUMMARY (sent every Sunday evening)
# ============================================================
def build_weekly_report(scan: dict) -> str:
    """Lighter weekly summary — top 3 sectors + top stock per sector."""
    pulse = scan.get("pulse", {})
    tops  = scan.get("top_sectors", [])[:3]
    dt    = scan.get("scan_dt", "—")

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "📅 *WEEKLY RS SUMMARY*",
        f"Week ending {dt[:10]}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"\nNifty RSI: {pulse.get('rsi',0):.1f} → {_mode_icon(pulse.get('mode','?'))}",
        "\n🏆 *This Week's Leaders:*",
    ]
    for s in tops:
        lines.append(f"  {s['rank']}. {s['sector']} | RS: {s['rs']:.3f} | {_pct_str(s['vs_nifty_pct'])}")

    ew = scan.get("emerg_weak", {})
    for e in ew.get("emerging_quarter", [])[:2]:
        lines.append(f"  ✅ {e['sector']} ({_pct_str(e['ret_90d'])} QTD)")

    lines.append("\n🩺 _BHARAT ALGOVERSE v3.0_")
    return "\n".join(lines)


# ============================================================
# MAIN SEND FUNCTION
# ============================================================
def send_daily_rs_report(report_type: str = "DAILY") -> bool:
    """
    Runs full scan and sends Telegram report.
    report_type: "DAILY" | "WEEKLY" | "MONTHLY"
    """
    log_terminal(f"[INVEST] Generating {report_type} RS report...", "INFO")

    try:
        scan = rs_engine.run_full_daily_scan(
            top_sectors_n=5,
            top_stocks_n=3,
            rs_period=int(db.get_param("invest_rs_period", "55") or "55"),
        )
    except Exception as e:
        msg = f"🔴 RS LegoMaster SCAN FAILED\nError: {e}"
        send_telegram_msg(msg)
        log_terminal(f"[INVEST] Scan failed: {e}", "ERROR")
        return False

    try:
        if report_type == "WEEKLY":
            report_text = build_weekly_report(scan)
        else:
            report_text = build_daily_report(scan)

        # Split into chunks if too long (Telegram 4096 limit)
        max_len = 4000
        if len(report_text) <= max_len:
            send_telegram_msg(report_text)
        else:
            chunks = [report_text[i:i+max_len] for i in range(0, len(report_text), max_len)]
            for chunk in chunks:
                send_telegram_msg(chunk)

        db.set_param("invest_last_report_dt", datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M"))
        log_terminal(f"[INVEST] {report_type} report sent via Telegram.", "INFO")
        return True

    except Exception as e:
        log_terminal(f"[INVEST] Report send failed: {e}", "ERROR")
        return False


if __name__ == "__main__":
    # Quick test: run and print report
    scan   = rs_engine.run_full_daily_scan(top_sectors_n=5, top_stocks_n=3)
    report = build_daily_report(scan)
    print(report)
