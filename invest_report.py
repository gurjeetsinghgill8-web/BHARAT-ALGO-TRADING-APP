"""
invest_report.py — BHARAT ALGOVERSE v3.1 | Telegram Report Engine
===================================================================
PUBLIC NAME: BHARAT MARKET COMPASS (BMC)
Internal: momentum-based sector rotation intelligence

⚠️  NEVER reveal RS values, RS formula, or RS thresholds in public reports.
    Language should be: "Leading", "Outperforming", "Strong Momentum"
    NOT: "RS: 1.187", "RS > 1.05 threshold"

Report Types:
  DAILY   → 8:00 AM IST, Mon-Fri
  WEEKLY  → Sunday 7:00 PM IST
  BSE     → Sensex-based report (separate series)

System Public Name: BHARAT MARKET COMPASS
Tagline: India's Institutional-Grade Market Intelligence
Valid: Reports are marked valid for 15 days from issue
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, date
import pytz

import db
import invest_rs_engine   as rs_engine
import invest_fundamentals as fund_eng
from utils import log_terminal, send_telegram_msg

IST = pytz.timezone("Asia/Kolkata")

# ── Public Branding (never change — hidden methodology) ─────
SYSTEM_NAME    = "BHARAT MARKET COMPASS"
SYSTEM_ICON    = "\U0001f9ed"   # 🧭
SYSTEM_TAGLINE = "India's Institutional-Grade Market Intelligence"
SYSTEM_VERSION = "BMC v3.1"
DISCLAIMER     = (
    "\u26a0\ufe0f *DISCLAIMER:* This is independent market research for "
    "educational purposes only. It is NOT investment advice. Past momentum "
    "does not guarantee future returns. Consult a SEBI-registered advisor "
    "before making any investment decision. Sector leadership can change — "
    "always use stop-losses."
)


# ════════════════════════════════════════════════════════════
# FINANCIAL METRICS FETCHER (yfinance — free)
# ════════════════════════════════════════════════════════════

def _fetch_financials(ticker: str) -> dict:
    """
    Fetch key financial metrics from yfinance.
    Returns dict with Revenue Growth, Profit Growth, ROE, ROCE, PE, D/E.
    Handles missing data gracefully.
    """
    out = {
        "revenue_growth":   None,
        "earnings_growth":  None,
        "roe":              None,
        "pe":               None,
        "pb":               None,
        "debt_equity":      None,
        "market_cap_cr":    None,
        "52w_change":       None,
    }
    try:
        info = yf.Ticker(ticker).info

        rg = info.get("revenueGrowth")
        eg = info.get("earningsGrowth")
        roe = info.get("returnOnEquity")
        pe  = info.get("trailingPE")
        pb  = info.get("priceToBook")
        de  = info.get("debtToEquity")
        mc  = info.get("marketCap")
        w52 = info.get("52WeekChange")

        if rg  is not None: out["revenue_growth"]  = round(rg  * 100, 1)
        if eg  is not None: out["earnings_growth"] = round(eg  * 100, 1)
        if roe is not None: out["roe"]             = round(roe * 100, 1)
        if pe  is not None: out["pe"]              = round(float(pe), 1)
        if pb  is not None: out["pb"]              = round(float(pb), 1)
        if de  is not None: out["debt_equity"]     = round(float(de) / 100, 2)
        if mc  is not None: out["market_cap_cr"]   = round(float(mc) / 1e7, 0)  # Convert to Crores
        if w52 is not None: out["52w_change"]      = round(float(w52) * 100, 1)
    except Exception as _e:
        log_terminal(f"[REPORT] Financials fetch skip {ticker}: {_e}", "WARN")
    return out


def _fmt_fin(val, suffix="", prefix="", positive_good=True) -> str:
    """Format a financial value with color emoji."""
    if val is None:
        return "N/A"
    if suffix == "%":
        if positive_good:
            icon = "\U0001f4c8" if val > 15 else "\U0001f4ca" if val < 0 else "\u27a1\ufe0f"
        else:
            icon = "\U0001f4ca" if val > 0 else "\U0001f4c8"
        return f"{icon} {prefix}{val:+.1f}{suffix}"
    return f"{prefix}{val}{suffix}"


# ════════════════════════════════════════════════════════════
# SECTOR STRENGTH LANGUAGE (never reveal RS formula)
# ════════════════════════════════════════════════════════════

def _strength_label(vs_nifty_pct: float) -> str:
    """Convert outperformance % to human language (no RS values)."""
    if vs_nifty_pct >= 20:
        return "\U0001f525 DOMINANT OUTPERFORMER"
    elif vs_nifty_pct >= 12:
        return "\U0001f7e2\U0001f7e2 STRONG LEADER"
    elif vs_nifty_pct >= 6:
        return "\U0001f7e2 OUTPERFORMER"
    elif vs_nifty_pct >= 2:
        return "\U0001f7e1 EMERGING LEADER"
    elif vs_nifty_pct >= -3:
        return "\u26aa IN LINE WITH MARKET"
    else:
        return "\U0001f534 UNDERPERFORMER"


def _stock_strength(vs_nifty_pct: float) -> str:
    if vs_nifty_pct >= 40:
        return "\U0001f525 Exceptional momentum"
    elif vs_nifty_pct >= 20:
        return "\U0001f7e2\U0001f7e2 Very strong"
    elif vs_nifty_pct >= 10:
        return "\U0001f7e2 Outperforming"
    else:
        return "\u27a1\ufe0f Moderate"


def _allocation_reason(sector_name: str, sector_pct: float) -> str:
    """Why this allocation % for this sector."""
    thesis = fund_eng.get_sector_thesis(sector_name)
    reasons = thesis.get("reasons", [])
    short   = thesis.get("short", "")
    # Take first 2 reasons as justification
    top2 = reasons[:2] if len(reasons) >= 2 else reasons
    lines = [f"Why {sector_pct:.0f}%? {short}"]
    for r in top2:
        # Strip emoji for cleaner text
        clean = r.strip()
        lines.append(f"  {clean}")
    return "\n".join(lines)


def _projection_text(fin: dict, sector_name: str) -> str:
    """Generate projection text from financial metrics."""
    lines = []
    rg = fin.get("revenue_growth")
    eg = fin.get("earnings_growth")
    roe = fin.get("roe")
    de  = fin.get("debt_equity")
    pe  = fin.get("pe")

    if rg and rg > 20:
        lines.append(f"Revenue accelerating at {rg:+.0f}% — analyst upgrades expected")
    if eg and eg > 25:
        lines.append(f"Earnings up {eg:+.0f}% YoY — institutional accumulation likely")
    if roe and roe > 20:
        lines.append(f"ROE {roe:.0f}% — high capital efficiency supports premium valuation")
    if de and de < 0.3:
        lines.append("Clean balance sheet — capacity expansion without dilution risk")
    if pe and pe < 20:
        lines.append(f"Trading at PE {pe:.0f}x — undervalued vs sector, re-rating potential")
    if not lines:
        thesis = fund_eng.get_sector_thesis(sector_name)
        lines.append(thesis.get("short", "Sector momentum sustained — monitor weekly"))
    return " | ".join(lines[:2])


# ════════════════════════════════════════════════════════════
# UNDERDOG DETECTOR
# ════════════════════════════════════════════════════════════

def _find_underdogs(all_scan_data: dict, n: int = 4) -> list[dict]:
    """
    Underdogs: small/mid caps with exceptionally strong momentum
    but low market coverage. Filter: vs_nifty_pct >= 30%.
    """
    underdogs = []
    for sector_name, stocks in all_scan_data.get("top_stocks", {}).items():
        for st in stocks:
            if st.get("cap") in ("Small", "Mid") and st.get("vs_nifty_pct", 0) >= 30:
                underdogs.append({**st, "sector": sector_name})
    # Also check ALL scanned stocks for high outperformers
    # Sort by outperformance
    underdogs.sort(key=lambda x: x.get("vs_nifty_pct", 0), reverse=True)
    # Remove duplicates
    seen = set()
    unique = []
    for u in underdogs:
        if u["symbol"] not in seen:
            seen.add(u["symbol"])
            unique.append(u)
    return unique[:n]


# ════════════════════════════════════════════════════════════
# REPORT BUILDERS
# ════════════════════════════════════════════════════════════

def build_daily_report(scan_data: dict) -> str:
    """
    Build full daily NSE report text (Telegram-ready Markdown).
    Does NOT include RS values — uses momentum language only.
    """
    now_str    = datetime.now(IST).strftime("%d %b %Y %H:%M IST")
    valid_till = (datetime.now(IST) + timedelta(days=15)).strftime("%d %b %Y")
    pulse      = scan_data.get("pulse", {})
    top_secs   = scan_data.get("top_sectors", [])
    top_stocks = scan_data.get("top_stocks", {})
    allocation = scan_data.get("allocation", {})
    em_weak    = scan_data.get("emerg_weak", {})
    underdogs  = _find_underdogs(scan_data)

    lines = []

    # ── Header ────────────────────────────────────────────────
    lines += [
        f"\u2501" * 32,
        f"{SYSTEM_ICON} *{SYSTEM_NAME}*",
        f"\U0001f4c5 Daily Intelligence Report | {now_str}",
        f"\u2501" * 32,
        "",
    ]

    # ── Market Pulse ──────────────────────────────────────────
    rsi_val  = pulse.get("rsi", 0)
    mode     = pulse.get("mode", "UNKNOWN")
    nifty_px = pulse.get("close", 0)
    if mode == "AGGRESSIVE":
        mode_txt = "\U0001f7e2 POSITIVE MOMENTUM\n\u2705 Market above key threshold — Stay invested. Ride momentum."
    else:
        mode_txt = "\U0001f534 CAUTION\n\u26a0\ufe0f Market below key threshold — Reduce risk. Protect capital."

    lines += [
        "\U0001f4c8 *MARKET PULSE*",
        f"Nifty 50: \u20b9{nifty_px:,.0f}",
        f"Trend Signal: {mode_txt}",
        "",
    ]

    # ── Sector Leadership Board ───────────────────────────────
    lines += [
        "\U0001f3c6 *SECTOR LEADERSHIP BOARD*",
        "_Sectors consistently beating the broader Indian market:_",
        "",
    ]
    for i, sec in enumerate(top_secs, 1):
        pct    = sec.get("vs_nifty_pct", 0)
        label  = _strength_label(pct)
        thesis = fund_eng.get_sector_thesis(sec["sector"])
        reasons = thesis.get("reasons", [])[:3]

        lines += [
            f"{i}\\. {label}",
            f"*{sec['sector'].replace('Nifty ','').upper()}*",
        ]
        # Catalyst (why running)
        for r in reasons:
            lines.append(f"  {r}")
        lines.append(f"  \U0001f4cb *Outlook:* {thesis.get('short','')}")
        lines.append("")

        # Top stocks for this sector
        stocks = top_stocks.get(sec["sector"], [])[:3]
        if stocks:
            lines.append(f"  \U0001f3af *Top Picks — {sec['sector'].replace('Nifty ','')}:*")
            for st in stocks:
                fin      = _fetch_financials(st["ticker"])
                st_label = _stock_strength(st.get("vs_nifty_pct", 0))
                cap_icon = {"Large": "\U0001f3e6", "Mid": "\U0001f3e2", "Small": "\U0001f3ea"}.get(st["cap"], "\U0001f4b0")

                lines += [
                    f"  {cap_icon} *{st['symbol']}* — {st['cap']} Cap | {st_label}",
                ]

                # Financial metrics
                fin_parts = []
                if fin.get("revenue_growth") is not None:
                    fin_parts.append(f"Revenue Growth: {fin['revenue_growth']:+.0f}%")
                if fin.get("earnings_growth") is not None:
                    fin_parts.append(f"Profit Growth: {fin['earnings_growth']:+.0f}%")
                if fin.get("roe") is not None:
                    fin_parts.append(f"ROE: {fin['roe']:.0f}%")
                if fin.get("debt_equity") is not None:
                    fin_parts.append(f"D/E: {fin['debt_equity']:.1f}x")
                if fin.get("pe") is not None:
                    fin_parts.append(f"PE: {fin['pe']:.0f}x")
                if fin_parts:
                    lines.append("  \U0001f4ca `" + " | ".join(fin_parts) + "`")

                # Projection
                proj = _projection_text(fin, sec["sector"])
                lines.append(f"  \U0001f52e *Projection:* {proj}")
                lines.append("")

        lines.append("\u2501" * 20)
        lines.append("")

    # ── Emerging vs Weak ──────────────────────────────────────
    emerging = em_weak.get("emerging_quarter", [])
    weak     = em_weak.get("weak_quarter", [])

    lines += ["", "\U0001f50d *SECTOR MOMENTUM TRACKER* _(Last 90 Days)_", ""]
    if emerging:
        lines.append("\u2705 *Rising Sectors — Momentum Building:*")
        for e in emerging:
            th  = fund_eng.get_sector_thesis(e["sector"])
            cat = th.get("reasons", ["Strong institutional buying"])[0] if th.get("reasons") else ""
            lines.append(
                f"  \U0001f7e2 *{e['sector'].replace('Nifty ','')}*: "
                f"+{e['ret_90d']:.1f}% | _{cat}_"
            )

    lines.append("")
    if weak:
        lines.append("\u274c *Sectors to Avoid — Losing Momentum:*")
        for w in weak:
            th   = fund_eng.get_sector_thesis(w["sector"])
            risk = th.get("risk", "Sector underperforming — avoid new positions")
            lines.append(
                f"  \U0001f534 *{w['sector'].replace('Nifty ','')}*: "
                f"{w['ret_90d']:+.1f}% | _{risk}_"
            )

    # ── Allocation Intelligence ───────────────────────────────
    if allocation:
        lines += ["", "\U0001f4b0 *ALLOCATION INTELLIGENCE*", "_Why these sector weights?_", ""]
        cap_counts = {"Large": 0, "Mid": 0, "Small": 0}
        for sec_name, alloc in allocation.items():
            sec_pct = alloc.get("sector_pct", 0)
            thesis  = fund_eng.get_sector_thesis(sec_name)
            reasons = thesis.get("reasons", [])

            lines += [
                f"\U0001f4ca *{sec_name.replace('Nifty ','')}* \u2192 {sec_pct:.0f}% of portfolio",
            ]
            # Why this weight
            if reasons:
                lines.append(f"  \u2192 {reasons[0]}")
            if len(reasons) > 1:
                lines.append(f"  \u2192 {reasons[1]}")

            for st_alloc in alloc.get("stocks", []):
                st_sym = st_alloc.get("symbol", "")
                pct    = st_alloc.get("alloc_pct", 0)
                cap    = st_alloc.get("cap", "")
                cap_icon = {"Large": "\U0001f3e6", "Mid": "\U0001f3e2", "Small": "\U0001f3ea"}.get(cap, "")
                lines.append(f"  {cap_icon} {st_sym}: {pct:.1f}%")
                cap_counts[cap] = cap_counts.get(cap, 0) + 1
            lines.append("")

        total_s = sum(cap_counts.values())
        lines.append(
            f"  Cap Mix: \U0001f3e6Large {cap_counts['Large']} | "
            f"\U0001f3e2Mid {cap_counts['Mid']} | "
            f"\U0001f3eaSmall {cap_counts['Small']} "
            f"(of {total_s} stocks)"
        )

    # ── Underdog Radar ────────────────────────────────────────
    if underdogs:
        lines += [
            "", "\U0001f680 *UNDERDOG RADAR*",
            "_Hidden momentum — strong stocks flying under the radar:_", "",
        ]
        for ud in underdogs:
            fin    = _fetch_financials(ud["ticker"])
            thesis = fund_eng.get_sector_thesis(ud.get("sector", ""))
            cat    = thesis.get("reasons", ["Sector tailwind supporting stock"])[0] if thesis.get("reasons") else ""

            fin_parts = []
            if fin.get("revenue_growth") is not None:
                fin_parts.append(f"Rev +{fin['revenue_growth']:.0f}%")
            if fin.get("earnings_growth") is not None:
                fin_parts.append(f"PAT +{fin['earnings_growth']:.0f}%")
            if fin.get("roe") is not None:
                fin_parts.append(f"ROE {fin['roe']:.0f}%")

            lines += [
                f"\U0001f4cd *{ud['symbol']}* | {ud['cap']} Cap | {ud.get('sector','').replace('Nifty ','')}",
                f"  \U0001f4c8 Strongly beating market | Moving quietly",
                f"  \U0001f4a1 {cat}",
            ]
            if fin_parts:
                lines.append("  \U0001f4ca `" + " | ".join(fin_parts) + "`")
            lines.append(
                f"  \u26a0\ufe0f Risk: Small/Mid cap = higher volatility. Size position accordingly."
            )
            lines.append("")

    # ── Footer ────────────────────────────────────────────────
    lines += [
        "\u2501" * 32,
        DISCLAIMER,
        "",
        f"\U0001f4c5 *Valid for 15 days* | Until: {valid_till}",
        f"\U0001f504 Next report: Tomorrow 8:00 AM IST",
        f"\n{SYSTEM_ICON} *{SYSTEM_NAME}* | {SYSTEM_VERSION}",
        "\u2501" * 32,
    ]

    return "\n".join(lines)


def build_weekly_report(scan_data: dict) -> str:
    """Weekly summary — broader market view."""
    now_str    = datetime.now(IST).strftime("%d %b %Y")
    top_secs   = scan_data.get("top_sectors", [])
    em_weak    = scan_data.get("emerg_weak", {})
    pulse      = scan_data.get("pulse", {})

    _bull = "BULLISH \U0001f7e2"
    _caut = "CAUTION \U0001f534"
    _trend = _bull if pulse.get("mode") == "AGGRESSIVE" else _caut
    lines = [
        "\u2501" * 32,
        f"{SYSTEM_ICON} *{SYSTEM_NAME} \u2014 WEEKLY OUTLOOK*",
        f"\U0001f4c5 Week of {now_str}",
        "\u2501" * 32, "",
        f"\U0001f4c8 Nifty: \u20b9{pulse.get('close',0):,.0f} | Trend: {_trend}",
        "",
        "\U0001f3c6 *SECTORS IN LEADERSHIP THIS WEEK:*",
    ]
    for i, sec in enumerate(top_secs, 1):
        label = _strength_label(sec.get("vs_nifty_pct", 0))
        lines.append(f"  {i}. *{sec['sector'].replace('Nifty ','')}* — {label}")

    emerging = em_weak.get("emerging_quarter", [])
    weak     = em_weak.get("weak_quarter", [])
    lines += ["", "\U0001f4cb *MOMENTUM SHIFTS:*"]
    for e in emerging:
        lines.append(f"  \u2b06\ufe0f {e['sector'].replace('Nifty ','')} ({e['ret_90d']:+.1f}% this quarter)")
    for w in weak:
        lines.append(f"  \u2b07\ufe0f {w['sector'].replace('Nifty ','')} ({w['ret_90d']:+.1f}% this quarter)")

    lines += [
        "",
        "_Full daily picks + stock analysis every morning 8AM._",
        "",
        DISCLAIMER,
        f"\n{SYSTEM_ICON} *{SYSTEM_NAME}* | {SYSTEM_VERSION}",
    ]
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# SEND FUNCTIONS
# ════════════════════════════════════════════════════════════

def send_daily_rs_report(report_type: str = "DAILY") -> bool:
    """Master function: run scan + build report + send Telegram."""
    log_terminal(f"[REPORT] Building {report_type} report...", "INFO")
    try:
        rs_period  = int(db.get_param("invest_rs_period", "55") or "55")
        scan_data  = rs_engine.run_full_daily_scan(rs_period=rs_period)
        if report_type == "WEEKLY":
            report_txt = build_weekly_report(scan_data)
        else:
            report_txt = build_daily_report(scan_data)

        # Telegram has 4096 char limit — send in chunks
        chunk_size = 4000
        chunks = [report_txt[i:i+chunk_size] for i in range(0, len(report_txt), chunk_size)]
        for chunk in chunks:
            send_telegram_msg(chunk)

        log_terminal(f"[REPORT] Sent {report_type} report ({len(report_txt)} chars).", "INFO")
        db.set_param("invest_last_report_dt", datetime.now(IST).strftime("%Y-%m-%d %H:%M"))
        return True
    except Exception as _e:
        log_terminal(f"[REPORT] Send failed: {_e}", "ERROR")
        return False
