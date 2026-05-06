"""
invest_query_engine.py — BHARAT ALGOVERSE v3.0 | Research AI Engine
=====================================================================
Natural-language query engine for Investment Research.
NO external LLM API — pure data + smart pattern matching.

Understands queries like:
  "Pichhle 2 saal mein kaun sa sector best tha?"
  "Agar main 1 lakh Auto mein lagata 6 mahine pahle, kitna milta?"
  "Kaun se sectors ne breakout diya is saal?"
  "IT sector ke top stocks 1 year mein?"
  "Top 3 sectors mein 5 lakh invest karta to abhi kitna hota?"

DB Namespace: invest_*  (read-only from here)
Data Source  : yfinance (free, full historical)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import pytz
import re
import db
from utils import log_terminal
import invest_rs_engine as rs_engine

IST = pytz.timezone("Asia/Kolkata")


# ════════════════════════════════════════════════════════════
# STEP 1: QUERY PARSER
# ════════════════════════════════════════════════════════════

def _extract_period_days(query: str) -> int:
    """Extracts time period in days from Hindi/English query."""
    q = query.lower()

    # Year patterns
    for pat in [r'(\d+)\s*(sal|saal|year|yr)', r'(ek|1)\s*(sal|saal|year)']:
        m = re.search(pat, q)
        if m:
            num = m.group(1)
            try:
                n = {"ek":1,"do":2,"teen":3,"char":4,"paanch":5}.get(num, int(num))
                return n * 365
            except: pass

    # Month patterns
    for pat in [r'(\d+)\s*(mahine|month|mah)', r'(ek|do|teen|char|chhe|barah)\s*(mahine|month)']:
        m = re.search(pat, q)
        if m:
            num = m.group(1)
            try:
                n = {"ek":1,"do":2,"teen":3,"char":4,"chhe":6,"barah":12}.get(num, int(num))
                return n * 30
            except: pass

    # Keyword fallbacks
    if any(x in q for x in ["quarter","tin mahine","3 mahine","90 din"]): return 90
    if any(x in q for x in ["half year","6 mahine","chhe mahine","aadhaa sal"]): return 180
    if any(x in q for x in ["2 sal","2 saal","do sal","2 year"]): return 730
    if any(x in q for x in ["5 sal","5 saal","paanch sal","5 year"]): return 1825
    if any(x in q for x in ["10 sal","das sal","10 year"]): return 3650

    return 365  # default 1 year


def _extract_amount(query: str) -> float:
    """Extracts investment amount in rupees."""
    q = query.lower().replace(",", "")

    # "X lakh" pattern
    m = re.search(r'(\d+(?:\.\d+)?)\s*lakh', q)
    if m:
        return float(m.group(1)) * 100000

    # "X crore" pattern
    m = re.search(r'(\d+(?:\.\d+)?)\s*crore', q)
    if m:
        return float(m.group(1)) * 10000000

    # Plain number ≥ 1000
    m = re.search(r'(\d{4,})', q)
    if m:
        return float(m.group(1))

    return 100000  # default 1 lakh


def _extract_sector(query: str) -> str | None:
    """Finds a sector name mentioned in the query."""
    q = query.lower()
    sector_map = {
        "auto":          "Nifty Auto",
        "bank":          "Nifty Bank",
        "psu bank":      "Nifty PSU Bank",
        "it":            "Nifty IT",
        "pharma":        "Nifty Pharma",
        "fmcg":          "Nifty FMCG",
        "metal":         "Nifty Metal",
        "realty":        "Nifty Realty",
        "real estate":   "Nifty Realty",
        "energy":        "Nifty Energy",
        "infra":         "Nifty Infra",
        "media":         "Nifty Media",
        "midcap":        "Nifty Midcap 100",
        "smallcap":      "Nifty Smallcap",
        "finance":       "Nifty Finance",
        "consumption":   "Nifty Consumption",
        "commodity":     "Nifty Commodities",
    }
    for key, val in sector_map.items():
        if key in q:
            return val
    return None


def _classify_query(query: str) -> str:
    """Classifies query into an intent type."""
    q = query.lower()

    if any(x in q for x in ["invest", "lagata", "lagau", "lagata", "milta", "hota", "return", "lakh", "crore", "kitna"]):
        return "RETURN_CALC"
    if any(x in q for x in ["breakout", "break out", "upar gaya", "chal gaya", "surge"]):
        return "BREAKOUT"
    if any(x in q for x in ["top stock", "best stock", "kaun sa stock", "stock"]):
        return "TOP_STOCKS"
    if any(x in q for x in ["compare", "vs", "versus", "comparison"]):
        return "COMPARE"
    if any(x in q for x in ["portfolio", "allocation", "diversif"]):
        return "PORTFOLIO"
    if any(x in q for x in ["sector", "best sector", "top sector", "kaun sa sector",
                              "leading", "sabse achha", "sabse upar"]):
        return "BEST_SECTOR"
    if any(x in q for x in ["report", "summary", "weekly", "monthly"]):
        return "REPORT"

    return "BEST_SECTOR"  # default


# ════════════════════════════════════════════════════════════
# STEP 2: ANALYSIS HANDLERS
# ════════════════════════════════════════════════════════════

def _fetch_sector_returns(days: int) -> list[dict]:
    """Returns all sectors sorted by % return over N days."""
    results = []
    period_str = f"{days + 30}d"

    for name, ticker in rs_engine.SECTOR_INDICES.items():
        try:
            df = yf.download(ticker, period=period_str, interval="1d",
                             progress=False, auto_adjust=True)["Close"].dropna().squeeze()
            if len(df) < days:
                continue
            start_price = float(df.iloc[-days])
            end_price   = float(df.iloc[-1])
            ret_pct     = round((end_price / start_price - 1) * 100, 2)
            results.append({
                "sector":      name,
                "ticker":      ticker,
                "start_price": round(start_price, 2),
                "end_price":   round(end_price, 2),
                "return_pct":  ret_pct,
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["return_pct"], reverse=True)
    for i, r in enumerate(results, 1):
        r["rank"] = i
    return results


def handle_best_sector(query: str, days: int) -> str:
    """Which sectors performed best in the given period?"""
    log_terminal(f"[QUERY] Best sector analysis: {days}d", "INFO")
    sectors = _fetch_sector_returns(days)
    if not sectors:
        return "Data fetch karne mein problem hui. Thodi der mein try karo."

    period_label = f"{days//365} Saal" if days >= 365 else f"{days//30} Mahine"
    nifty_ret    = next((s["return_pct"] for s in sectors if "^NSEI" in s.get("ticker","")), None)

    # Fetch Nifty separately for reference
    try:
        ndf = yf.download("^NSEI", period=f"{days+30}d", interval="1d",
                          progress=False, auto_adjust=True)["Close"].dropna().squeeze()
        nifty_ret = round((float(ndf.iloc[-1]) / float(ndf.iloc[-days]) - 1) * 100, 2)
    except: nifty_ret = None

    lines = [
        f"📊 **SECTOR PERFORMANCE — Last {period_label}**",
        f"{'─'*45}",
    ]
    if nifty_ret is not None:
        lines.append(f"📈 Nifty 50 Return: **{nifty_ret:+.1f}%** (benchmark)")
        lines.append("")

    lines.append("🏆 **ALL SECTORS RANKED:**")
    for s in sectors:
        icon  = "🟢" if s["return_pct"] > 0 else "🔴"
        beat  = " ⭐ (beat Nifty)" if nifty_ret and s["return_pct"] > nifty_ret else ""
        lines.append(f"  {s['rank']:2d}. {icon} **{s['sector']}** → **{s['return_pct']:+.1f}%**{beat}")

    top3   = sectors[:3]
    bottom3= sectors[-3:]
    lines += [
        "",
        f"✅ **TOP 3 WINNERS:** {', '.join(s['sector'] for s in top3)}",
        f"❌ **BOTTOM 3 LOSERS:** {', '.join(s['sector'] for s in bottom3)}",
        "",
        f"*Data: NSE via yfinance | Period: {period_label}*"
    ]
    return "\n".join(lines)


def handle_return_calc(query: str, days: int, amount: float) -> str:
    """Agar X rupees invest karta to kitna milta?"""
    log_terminal(f"[QUERY] Return calc: Rs {amount:,.0f} over {days}d", "INFO")
    sectors = _fetch_sector_returns(days)
    if not sectors:
        return "Data fetch karne mein dikkat aayi."

    period_label = f"{days//365} Saal" if days >= 365 else f"{days//30} Mahine"
    sector_name  = _extract_sector(query)

    # Fetch Nifty return for comparison
    try:
        ndf = yf.download("^NSEI", period=f"{days+30}d", interval="1d",
                          progress=False, auto_adjust=True)["Close"].dropna().squeeze()
        nifty_ret_pct = (float(ndf.iloc[-1]) / float(ndf.iloc[-days]) - 1) * 100
        nifty_final   = amount * (1 + nifty_ret_pct / 100)
    except:
        nifty_ret_pct = 0
        nifty_final   = amount

    lines = [
        f"💰 **RETURN CALCULATOR — Rs {amount:,.0f} over {period_label}**",
        f"{'─'*45}",
        f"📌 *Agar aapne {period_label} pehle invest kiya hota...*",
        "",
    ]

    # If specific sector mentioned
    if sector_name:
        sec = next((s for s in sectors if s["sector"] == sector_name), None)
        if sec:
            final_val  = amount * (1 + sec["return_pct"] / 100)
            profit     = final_val - amount
            lines += [
                f"🎯 **{sector_name}:**",
                f"   Invested  : Rs {amount:,.0f}",
                f"   Return    : **{sec['return_pct']:+.1f}%**",
                f"   Final Value: **Rs {final_val:,.0f}**",
                f"   {'Profit' if profit >= 0 else 'Loss'}    : **Rs {abs(profit):,.0f}**",
                "",
            ]

    # Show top 5 with returns
    lines.append("🏆 **TOP 5 SECTORS — What you would have made:**")
    for s in sectors[:5]:
        final_val = amount * (1 + s["return_pct"] / 100)
        profit    = final_val - amount
        p_icon    = "🟢" if profit >= 0 else "🔴"
        lines.append(
            f"  {s['rank']}. {p_icon} **{s['sector']}** "
            f"({s['return_pct']:+.1f}%) → Rs {final_val:,.0f} "
            f"({'Profit' if profit>=0 else 'Loss'}: Rs {abs(profit):,.0f})"
        )

    lines += [
        "",
        f"📊 **vs Nifty 50 (Buy & Hold):** Rs {nifty_final:,.0f} ({nifty_ret_pct:+.1f}%)",
        "",
    ]

    # Smart conclusion
    best = sectors[0]
    best_final = amount * (1 + best["return_pct"] / 100)
    if best["return_pct"] > nifty_ret_pct:
        lines.append(
            f"💡 *Best bet would have been **{best['sector']}** — "
            f"Rs {amount:,.0f} → Rs {best_final:,.0f} "
            f"({best['return_pct']:+.1f}% vs Nifty {nifty_ret_pct:+.1f}%)*"
        )
    lines.append(f"\n*Data: NSE via yfinance | Period: {period_label}*")
    return "\n".join(lines)


def handle_breakout(query: str, days: int) -> str:
    """Which sectors gave breakouts in this period?"""
    log_terminal(f"[QUERY] Breakout analysis: {days}d", "INFO")
    sectors = _fetch_sector_returns(days)
    period_label = f"{days//365} Saal" if days >= 365 else f"{days//30} Mahine"

    # Breakout = return > 20% AND outperforming Nifty significantly
    try:
        ndf = yf.download("^NSEI", period=f"{days+30}d", interval="1d",
                          progress=False, auto_adjust=True)["Close"].dropna().squeeze()
        nifty_ret = (float(ndf.iloc[-1]) / float(ndf.iloc[-days]) - 1) * 100
    except: nifty_ret = 0

    breakouts  = [s for s in sectors if s["return_pct"] > max(20, nifty_ret + 10)]
    struggling = [s for s in sectors if s["return_pct"] < min(-5, nifty_ret - 10)]

    lines = [
        f"🚀 **BREAKOUT SECTORS — Last {period_label}**",
        f"Benchmark: Nifty 50 = {nifty_ret:+.1f}%",
        f"{'─'*45}",
        "",
    ]

    if breakouts:
        lines.append("✅ **BREAKOUT SECTORS (significantly beat Nifty):**")
        for s in breakouts:
            beat_by = s["return_pct"] - nifty_ret
            lines.append(f"  🚀 **{s['sector']}** → {s['return_pct']:+.1f}% (Nifty se {beat_by:+.1f}% aage)")
    else:
        lines.append("Koi significant breakout nahi mila is period mein.")

    lines.append("")
    if struggling:
        lines.append("⚠️ **WEAK / STRUGGLING SECTORS:**")
        for s in struggling:
            lines.append(f"  🔻 **{s['sector']}** → {s['return_pct']:+.1f}%")

    lines.append(f"\n*Data: NSE via yfinance | Period: {period_label}*")
    return "\n".join(lines)


def handle_top_stocks(query: str, days: int) -> str:
    """Top stocks in a sector for given period."""
    sector_name = _extract_sector(query) or "Nifty Auto"
    log_terminal(f"[QUERY] Top stocks: {sector_name} | {days}d", "INFO")

    period_label = f"{days//365} Saal" if days >= 365 else f"{days//30} Mahine"
    stocks = rs_engine.SECTOR_STOCKS.get(sector_name, [])
    if not stocks:
        return f"'{sector_name}' ke stocks ka data available nahi hai."

    results = []
    for ticker, cap in stocks:
        try:
            df = yf.download(ticker, period=f"{days+30}d", interval="1d",
                             progress=False, auto_adjust=True)["Close"].dropna().squeeze()
            if len(df) < days:
                continue
            ret = round((float(df.iloc[-1]) / float(df.iloc[-days]) - 1) * 100, 2)
            results.append({"symbol": ticker.replace(".NS",""), "cap": cap, "return_pct": ret})
        except: continue

    results.sort(key=lambda x: x["return_pct"], reverse=True)

    lines = [
        f"🎯 **TOP STOCKS: {sector_name} — Last {period_label}**",
        f"{'─'*45}",
    ]
    cap_icons = {"Large": "🏦", "Mid": "🏢", "Small": "🏪"}
    for i, s in enumerate(results, 1):
        icon  = cap_icons.get(s["cap"], "📦")
        trend = "🟢" if s["return_pct"] > 0 else "🔴"
        lines.append(
            f"  {i:2d}. {trend} {icon} **{s['symbol']}** ({s['cap']} Cap) → **{s['return_pct']:+.1f}%**"
        )

    if results:
        winner = results[0]
        lines += [
            "",
            f"🏆 *Winner: **{winner['symbol']}** with {winner['return_pct']:+.1f}% in {period_label}*"
        ]
    lines.append(f"\n*Data: NSE via yfinance | Period: {period_label}*")
    return "\n".join(lines)


def handle_portfolio(query: str, days: int, amount: float) -> str:
    """If invested equally in top 3 sectors, what would happen?"""
    log_terminal(f"[QUERY] Portfolio backtest: Rs {amount:,.0f} | {days}d", "INFO")
    sectors = _fetch_sector_returns(days)
    if not sectors: return "Data fetch dikkat."

    period_label = f"{days//365} Saal" if days >= 365 else f"{days//30} Mahine"
    top3  = sectors[:3]
    alloc = amount / 3  # equal allocation

    total_final = sum(alloc * (1 + s["return_pct"] / 100) for s in top3)
    total_profit = total_final - amount
    total_ret_pct= (total_final / amount - 1) * 100

    try:
        ndf = yf.download("^NSEI", period=f"{days+30}d", interval="1d",
                          progress=False, auto_adjust=True)["Close"].dropna().squeeze()
        nifty_ret = (float(ndf.iloc[-1]) / float(ndf.iloc[-days]) - 1) * 100
        nifty_final = amount * (1 + nifty_ret / 100)
    except:
        nifty_ret = 0; nifty_final = amount

    lines = [
        f"📊 **PORTFOLIO BACKTEST — Top 3 Sectors | {period_label}**",
        f"Total Investment: Rs {amount:,.0f} (Rs {alloc:,.0f} each sector)",
        f"{'─'*45}",
        "",
        "**Allocation:**",
    ]
    for s in top3:
        final_val = alloc * (1 + s["return_pct"] / 100)
        profit    = final_val - alloc
        lines.append(
            f"  📌 **{s['sector']}** (Rs {alloc:,.0f})"
            f" → Rs {final_val:,.0f} ({s['return_pct']:+.1f}%)"
        )

    lines += [
        "",
        f"💰 **TOTAL PORTFOLIO:**",
        f"   Invested  : Rs {amount:,.0f}",
        f"   Final     : **Rs {total_final:,.0f}**",
        f"   {'Profit' if total_profit>=0 else 'Loss'}: **Rs {abs(total_profit):,.0f}** ({total_ret_pct:+.1f}%)",
        "",
        f"📈 **vs Nifty 50 (Buy & Hold):** Rs {nifty_final:,.0f} ({nifty_ret:+.1f}%)",
        f"   Difference: Rs {(total_final - nifty_final):+,.0f} {'(You Beat Nifty! 🏆)' if total_final > nifty_final else '(Nifty better this time)'}",
        "",
        f"*Data: NSE via yfinance | Period: {period_label}*"
    ]
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# STEP 3: MASTER QUERY PROCESSOR
# ════════════════════════════════════════════════════════════

def process_query(query: str) -> str:
    """
    Main entry point. Takes a natural language query,
    routes to the right handler, returns formatted report.
    """
    if not query or len(query.strip()) < 3:
        return "Kuch poochho! Jaise: 'Pichhle 1 saal mein kaun sa sector best tha?'"

    log_terminal(f"[QUERY] Processing: {query[:80]}", "INFO")

    intent = _classify_query(query)
    days   = _extract_period_days(query)
    amount = _extract_amount(query)

    # Route to handler
    try:
        if intent == "RETURN_CALC":
            result = handle_return_calc(query, days, amount)
        elif intent == "BREAKOUT":
            result = handle_breakout(query, days)
        elif intent == "TOP_STOCKS":
            result = handle_top_stocks(query, days)
        elif intent == "PORTFOLIO":
            result = handle_portfolio(query, days, amount)
        elif intent == "BEST_SECTOR":
            result = handle_best_sector(query, days)
        else:
            result = handle_best_sector(query, days)

        # Append timestamp
        now = datetime.now(IST).strftime("%d %b %Y %I:%M %p IST")
        result += f"\n\n_⏱ Generated: {now}_"
        return result

    except Exception as e:
        log_terminal(f"[QUERY] Handler error: {e}", "ERROR")
        return (
            f"Analysis mein thodi problem aayi: `{str(e)[:120]}`\n\n"
            "Dobara try karo ya thoda alag tarike se poochho."
        )


# ════════════════════════════════════════════════════════════
# QUICK QUESTIONS (preset buttons)
# ════════════════════════════════════════════════════════════

QUICK_QUESTIONS = [
    ("📈 1 Saal Best Sector?",       "Pichhle 1 saal mein kaun sa sector sabse best tha?"),
    ("💰 1L → 1Y Return?",           "Agar main 1 lakh invest karta 1 saal pahle top sector mein kitna milta?"),
    ("🚀 6M Breakouts?",             "Pichhle 6 mahine mein kaun se sectors ne breakout diya?"),
    ("🏦 Auto Sector Stocks 1Y?",    "Auto sector ke top stocks pichhle 1 saal mein kaun se hain?"),
    ("📊 Portfolio Top3 5L 2Y?",     "Agar top 3 sectors mein 5 lakh 2 saal pahle lagata to kitna hota?"),
    ("🔍 2 Saal Weak Sectors?",      "Pichhle 2 saal mein kaun se sectors sabse weak the?"),
    ("🏥 Pharma Stocks 6M?",         "Pharma sector ke top stocks 6 mahine mein?"),
    ("💎 PSU Bank 1Y Return?",       "PSU Bank sector mein 2 lakh 1 saal pahle lagata to kitna hota?"),
]
