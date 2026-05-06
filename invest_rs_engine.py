"""
invest_rs_engine.py — BHARAT ALGOVERSE v3.0 | RS LegoMaster Engine
====================================================================
Module 3: Investment Analysis — Relative Strength Based System
Inspired by: Weinstein, Minervini, CAN SLIM adapted for Indian NSE

LEGO BLOCKS:
  1. Market Pulse     → Nifty 50 RSI(14) + Market Mode
  2. Sector Scanner   → RS-55 ranking of all NSE sectors vs Nifty
  3. Cap Classifier   → Large / Mid / Small cap tagging
  4. RS Engine        → 55-day Relative Strength per sector & stock
  5. Strength Ranker  → Sort sectors → rank stocks within sectors
  6. Allocation Calc  → Suggested % allocation per stock/sector
  7. Emerging Detector→ Quarterly/Yearly sector leaders & laggards

DB Namespace: invest_*   ← NEVER mix with nifty_* or crypto_*
Data Source  : yfinance (free, no subscription)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import db
from utils import log_terminal

IST = pytz.timezone("Asia/Kolkata")

# ============================================================
# NSE SECTOR INDEX MAP  (yfinance tickers)
# ============================================================
SECTOR_INDICES = {
    # ── NSE Nifty Sectors ──────────────────────────────────
    "Nifty Auto":       "^CNXAUTO",
    "Nifty Bank":       "^NSEBANK",
    "Nifty IT":         "^CNXIT",
    "Nifty Pharma":     "^CNXPHARMA",
    "Nifty FMCG":       "^CNXFMCG",
    "Nifty Metal":      "^CNXMETAL",
    "Nifty Realty":     "^CNXREALTY",
    "Nifty Energy":     "^CNXENERGY",
    "Nifty Infra":      "^CNXINFRA",
    "Nifty Media":      "^CNXMEDIA",
    "Nifty PSU Bank":   "^CNXPSUBANK",
    "Nifty Midcap 100": "^CNXMIDCAP",
    "Nifty Smallcap":   "^CNXSMALLCAP",
    "Nifty PSE":        "^CNXPSE",
    "Nifty MNC":        "^CNXMNC",
    "Nifty Service":    "^CNXSERVICE",
    "Nifty Commodities":"^CNXCOMMODITIES",
    "Nifty Consumption":"^CNXCONSUMPTION",
    "Nifty Finance":    "^CNXFINANCE",
    "Nifty CPSE":       "^CNXCPSE",
    # ── Defence (New) ──────────────────────────────────────
    "Nifty Defence":    "^CNXDEFENCE",   # Nifty India Defence Index
}

# ── BSE Sensex Sectors (separate report — deeper coverage) ──
BSE_SECTOR_INDICES = {
    "BSE Auto":          "^BSEAUTO",
    "BSE Bankex":        "^SPIBANKEX",
    "BSE IT":            "^BSEIT",
    "BSE Healthcare":    "^BSEHC",
    "BSE FMCG":          "^BSEFMCG",
    "BSE Metal":         "^BSEMETAL",
    "BSE Realty":        "^BSEREALTY",
    "BSE Oil & Gas":     "^BSEOILGAS",
    "BSE Power":         "^BSEPOWER",
    "BSE Capital Goods": "^BSECG",
    "BSE Consumer Dur":  "^BSECD",
    "BSE Telecom":       "^BSETECK",
}

# ============================================================
# TOP STOCKS BY SECTOR (Large/Mid/Small Cap, .NS suffix)
# ============================================================
SECTOR_STOCKS = {
    "Nifty Auto":    [
        ("TATAMOTORS.NS","Large"), ("M&M.NS","Large"), ("MARUTI.NS","Large"),
        ("BAJAJ-AUTO.NS","Large"), ("EICHERMOT.NS","Large"), ("HEROMOTOCO.NS","Large"),
        ("BOSCHLTD.NS","Mid"),    ("MOTHERSON.NS","Mid"), ("BALKRISIND.NS","Mid"),
    ],
    "Nifty Bank":    [
        ("HDFCBANK.NS","Large"), ("ICICIBANK.NS","Large"), ("KOTAKBANK.NS","Large"),
        ("AXISBANK.NS","Large"), ("INDUSINDBK.NS","Large"),
        ("FEDERALBNK.NS","Mid"), ("BANDHANBNK.NS","Mid"), ("IDFCFIRSTB.NS","Mid"),
    ],
    "Nifty IT":      [
        ("TCS.NS","Large"), ("INFY.NS","Large"), ("HCLTECH.NS","Large"),
        ("WIPRO.NS","Large"), ("TECHM.NS","Large"),
        ("LTIM.NS","Mid"), ("MPHASIS.NS","Mid"), ("PERSISTENT.NS","Mid"),
    ],
    "Nifty Pharma":  [
        ("SUNPHARMA.NS","Large"), ("DRREDDY.NS","Large"), ("CIPLA.NS","Large"),
        ("DIVISLAB.NS","Large"), ("AUROPHARMA.NS","Mid"), ("ALKEM.NS","Mid"),
        ("IPCALAB.NS","Mid"), ("NATCOPHARM.NS","Small"),
    ],
    "Nifty FMCG":    [
        ("HINDUNILVR.NS","Large"), ("ITC.NS","Large"), ("NESTLEIND.NS","Large"),
        ("BRITANNIA.NS","Large"), ("DABUR.NS","Large"),
        ("MARICO.NS","Mid"), ("GODREJCP.NS","Mid"),
    ],
    "Nifty Metal":   [
        ("TATASTEEL.NS","Large"), ("JSWSTEEL.NS","Large"), ("HINDALCO.NS","Large"),
        ("VEDL.NS","Large"), ("SAIL.NS","Large"),
        ("NATIONALUM.NS","Mid"), ("RATNAMANI.NS","Mid"),
    ],
    "Nifty Realty":  [
        ("DLF.NS","Large"), ("GODREJPROP.NS","Large"), ("PRESTIGE.NS","Mid"),
        ("OBEROIRLTY.NS","Mid"), ("PHOENIXLTD.NS","Mid"), ("BRIGADE.NS","Mid"),
        ("SUNTECK.NS","Small"),
    ],
    "Nifty Energy":  [
        ("RELIANCE.NS","Large"), ("ONGC.NS","Large"), ("NTPC.NS","Large"),
        ("POWERGRID.NS","Large"), ("ADANIGREEN.NS","Large"),
        ("CESC.NS","Mid"), ("TORNTPOWER.NS","Mid"),
    ],
    "Nifty PSU Bank":[
        ("SBIN.NS","Large"), ("BANKBARODA.NS","Large"), ("CANBK.NS","Large"),
        ("PNB.NS","Large"), ("UNIONBANK.NS","Mid"), ("INDIANB.NS","Mid"),
    ],
    "Nifty Infra":   [
        ("LT.NS","Large"), ("ADANIPORTS.NS","Large"), ("IRFC.NS","Large"),
        ("RVNL.NS","Mid"), ("IRCON.NS","Mid"), ("NBCC.NS","Mid"),
        ("KEC.NS","Mid"), ("KALPATPOWR.NS","Small"),
    ],
    "Nifty Finance": [
        ("BAJFINANCE.NS","Large"), ("BAJAJFINSV.NS","Large"), ("HDFCAMC.NS","Large"),
        ("LICIHSGFIN.NS","Large"), ("MUTHOOTFIN.NS","Mid"), ("CHOLAFIN.NS","Mid"),
        ("M&MFIN.NS","Mid"),
    ],
    "Nifty Media":   [
        ("ZEEL.NS","Mid"), ("SUNTV.NS","Mid"), ("NETWORK18.NS","Mid"),
        ("PVR.NS","Small"), ("INOXLEISUR.NS","Small"),
    ],
    "Nifty Midcap 100":  [
        ("CAMS.NS","Mid"), ("ANGELONE.NS","Mid"), ("POLICYBZR.NS","Mid"),
        ("PAYTM.NS","Mid"), ("NYKAA.NS","Mid"),
    ],
    # ── Defence (New) ──────────────────────────────────────
    "Nifty Defence":    [
        ("HAL.NS","Large"),        # Hindustan Aeronautics — aircraft + engines
        ("BEL.NS","Large"),        # Bharat Electronics — radar, defence systems
        ("BEML.NS","Mid"),         # BEML — mining + defence vehicles
        ("COCHINSHIP.NS","Mid"),   # Cochin Shipyard — naval vessels
        ("MAZDOCK.NS","Mid"),      # Mazagon Dock — submarine builder
        ("MTAR.NS","Small"),       # MTAR Technologies — defence components
        ("PARAS.NS","Small"),      # Paras Defence — space & defence optics
    ],
}


NIFTY_TICKER = "^NSEI"
RS_PERIOD    = 55   # Primary RS period (days)
RSI_PERIOD   = 14   # RSI for Nifty pulse


# ============================================================
# LEGO 1: Market Pulse — Nifty RSI
# ============================================================
def _calc_rsi(series: pd.Series, period: int = 14) -> float:
    """Wilder's RSI."""
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def get_market_pulse() -> dict:
    """
    Returns Nifty RSI + market mode.
    mode: 'AGGRESSIVE' (RSI>50) or 'DEFENSIVE' (RSI<=50)
    """
    try:
        data = yf.download(NIFTY_TICKER, period="3mo", interval="1d",
                           progress=False, auto_adjust=True)
        if data.empty or len(data) < RSI_PERIOD + 5:
            return {"rsi": 0, "mode": "UNKNOWN", "close": 0, "error": "Insufficient data"}

        close = data["Close"].dropna().squeeze()
        rsi   = _calc_rsi(close, RSI_PERIOD)
        last  = float(close.iloc[-1])
        mode  = "AGGRESSIVE" if rsi > 50 else "DEFENSIVE"
        log_terminal(f"[INVEST] Nifty RSI: {rsi} → {mode}", "INFO")
        db.set_param("invest_nifty_rsi",  str(rsi))
        db.set_param("invest_market_mode", mode)
        return {"rsi": rsi, "mode": mode, "close": round(last, 2), "error": None}
    except Exception as e:
        log_terminal(f"[INVEST] Market pulse error: {e}", "ERROR")
        return {"rsi": 0, "mode": "UNKNOWN", "close": 0, "error": str(e)}


# ============================================================
# LEGO 2: RS Engine — Relative Strength Calculation
# ============================================================
def calc_rs(ticker: str, benchmark: str = NIFTY_TICKER,
            period: int = RS_PERIOD) -> float | None:
    """
    RS = (Ticker_Today / Ticker_N_days_ago)
         / (Benchmark_Today / Benchmark_N_days_ago)
    RS > 1.0 → Outperforming benchmark
    """
    try:
        lookback = f"{period + 20}d"
        df = yf.download([ticker, benchmark], period=lookback, interval="1d",
                         progress=False, auto_adjust=True)["Close"]
        if df.empty or ticker not in df.columns or benchmark not in df.columns:
            return None
        df = df.dropna()
        if len(df) < period + 2:
            return None
        stock_rs = float(df[ticker].iloc[-1]) / float(df[ticker].iloc[-period])
        nifty_rs = float(df[benchmark].iloc[-1]) / float(df[benchmark].iloc[-period])
        if nifty_rs == 0:
            return None
        rs = round(stock_rs / nifty_rs, 4)
        return rs
    except Exception as e:
        log_terminal(f"[INVEST] RS calc error {ticker}: {e}", "ERROR")
        return None


# ============================================================
# LEGO 3: Sector Scanner — Rank all sectors by RS-55
# ============================================================
def scan_sectors(period: int = RS_PERIOD) -> list[dict]:
    """
    Returns list of sectors sorted by RS descending.
    Each: {name, ticker, rs, vs_nifty_pct, outperforming}
    """
    results = []
    for name, ticker in SECTOR_INDICES.items():
        rs = calc_rs(ticker, NIFTY_TICKER, period)
        if rs is None:
            continue
        results.append({
            "sector":        name,
            "ticker":        ticker,
            "rs":            rs,
            "vs_nifty_pct":  round((rs - 1.0) * 100, 2),
            "outperforming": rs > 1.0,
        })

    results.sort(key=lambda x: x["rs"], reverse=True)

    # Add rank
    for i, r in enumerate(results, 1):
        r["rank"] = i

    log_terminal(f"[INVEST] Scanned {len(results)} sectors.", "INFO")
    return results


# ============================================================
# LEGO 4: Stock RS within Sector — ranked list
# ============================================================
def scan_stocks_in_sector(sector_name: str,
                           period: int = RS_PERIOD) -> list[dict]:
    """
    Returns top stocks in a sector ranked by RS-55.
    Each: {symbol, cap, rs, vs_nifty_pct}
    """
    stocks = SECTOR_STOCKS.get(sector_name, [])
    if not stocks:
        return []

    results = []
    for symbol, cap in stocks:
        rs = calc_rs(symbol, NIFTY_TICKER, period)
        if rs is None:
            continue
        results.append({
            "symbol":       symbol.replace(".NS", ""),
            "ticker":       symbol,
            "cap":          cap,
            "sector":       sector_name,
            "rs":           rs,
            "vs_nifty_pct": round((rs - 1.0) * 100, 2),
            "outperforming": rs > 1.0,
        })

    # Sort: by RS desc, large caps preferred
    cap_order = {"Large": 0, "Mid": 1, "Small": 2}
    results.sort(key=lambda x: (-x["rs"], cap_order.get(x["cap"], 3)))

    for i, r in enumerate(results, 1):
        r["rank"] = i

    return results


# ============================================================
# LEGO 5: Allocation Calculator
# ============================================================
def calc_allocation(top_sectors: list[dict],
                    top_stocks_by_sector: dict) -> dict:
    """
    Allocates capital % based on sector RS strength.
    Rule:
      - Top sector gets highest weight proportional to RS
      - Within sector: Large > Mid > Small cap
      - Max single stock: 25% | Min: 5%
    Returns: {sector → [{symbol, alloc_%}]}
    """
    if not top_sectors:
        return {}

    # Sector weights proportional to RS
    total_rs   = sum(s["rs"] for s in top_sectors)
    alloc_out  = {}

    for s in top_sectors:
        sector_pct = round((s["rs"] / total_rs) * 100, 1)
        stocks     = top_stocks_by_sector.get(s["sector"], [])
        if not stocks:
            continue

        # Within sector: proportional to stock RS
        stock_total_rs = sum(st["rs"] for st in stocks)
        stock_allocs   = []
        for st in stocks:
            raw_pct  = (st["rs"] / stock_total_rs) * sector_pct if stock_total_rs else 0
            clipped  = max(5.0, min(25.0, round(raw_pct, 1)))
            stock_allocs.append({**st, "alloc_pct": clipped})

        alloc_out[s["sector"]] = {
            "sector_pct":  sector_pct,
            "stocks":      stock_allocs,
        }

    return alloc_out


# ============================================================
# LEGO 6: Emerging vs Weak Sectors (Quarterly / Yearly)
# ============================================================
def detect_emerging_weak(top_n: int = 3) -> dict:
    """
    Compares sector performance over last 90d (quarter) and 365d (year).
    Returns emerging (top gainers) and weak (bottom) sectors.
    """
    results = []
    for name, ticker in SECTOR_INDICES.items():
        try:
            df = yf.download(ticker, period="13mo", interval="1d",
                             progress=False, auto_adjust=True)["Close"].dropna().squeeze()
            if len(df) < 60:
                continue

            # Returns
            ret_90d  = round((float(df.iloc[-1]) / float(df.iloc[-90])  - 1) * 100, 2) if len(df) >= 90  else None
            ret_365d = round((float(df.iloc[-1]) / float(df.iloc[-250]) - 1) * 100, 2) if len(df) >= 250 else None
            results.append({"sector": name, "ret_90d": ret_90d, "ret_365d": ret_365d})
        except Exception:
            continue

    valid = [r for r in results if r["ret_90d"] is not None]
    valid.sort(key=lambda x: x["ret_90d"], reverse=True)

    return {
        "emerging_quarter": valid[:top_n],
        "weak_quarter":     valid[-top_n:],
        "all":              valid,
    }


# ============================================================
# LEGO 7: Full Daily Scan (Master Function)
# ============================================================
def run_full_daily_scan(top_sectors_n: int = 5,
                        top_stocks_n:  int = 3,
                        rs_period:     int = RS_PERIOD) -> dict:
    """
    Runs the complete RS LegoMaster daily scan.
    Returns a structured dict with everything for the report.
    """
    log_terminal("[INVEST] Starting full RS daily scan...", "INFO")

    # 1. Market Pulse
    pulse = get_market_pulse()

    # 2. Sector Scan
    all_sectors = scan_sectors(rs_period)
    strong_sectors = [s for s in all_sectors if s["outperforming"]][:top_sectors_n]

    # 3. Stock scan for top sectors
    top_stocks_by_sector = {}
    for sec in strong_sectors:
        stocks = scan_stocks_in_sector(sec["sector"], rs_period)
        top_stocks_by_sector[sec["sector"]] = stocks[:top_stocks_n]

    # 4. Allocation
    allocation = calc_allocation(strong_sectors, top_stocks_by_sector)

    # 5. Emerging / Weak
    emerg_weak = detect_emerging_weak(top_n=3)

    # 6. Save summary to DB
    db.set_param("invest_last_scan_dt", datetime.now(IST).strftime("%Y-%m-%d %H:%M"))
    db.set_param("invest_top_sectors",  str([s["sector"] for s in strong_sectors]))

    log_terminal("[INVEST] Daily scan complete.", "INFO")
    return {
        "pulse":       pulse,
        "all_sectors": all_sectors,
        "top_sectors": strong_sectors,
        "top_stocks":  top_stocks_by_sector,
        "allocation":  allocation,
        "emerg_weak":  emerg_weak,
        "scan_dt":     datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
        "rs_period":   rs_period,
    }
