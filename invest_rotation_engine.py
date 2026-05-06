"""
invest_rotation_engine.py — BHARAT ALGOVERSE v3.1 | RS Rotation Engine
=======================================================================
Rolling Sector Rotation Backtest — the CORRECT way.

LEGO BLOCKS:
  1. Market Gate     → Nifty RSI weekly check
  2. Sector Scanner  → RS-55 weekly rank of all sectors
  3. Leadership Mgr  → Enter / Hold / Exit with 5% buffer (RS < 0.95)
  4. Stock Picker    → 2 Large + 2 Mid + 2 Small per sector
  5. Backtest Engine → Weekly steps, compound capital, full trade log

CONFIRMED RULES (Dr. Saab — 2026-05-06):
  Exit buffer    : RS < 0.95 (5% below 1.0)
  Max sectors    : 2 parallel
  Cash rule      : 100% cash when no strong sector
  Reentry        : Yes, after 4-week (28-day) gap minimum
  Stock exit     : Hybrid — if stock's own RS > 1.0 at sector exit,
                   give 2-week grace period, then force exit

Data source    : yfinance (all data downloaded upfront for speed)
DB namespace   : invest_*
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import pytz
import json
import db
from utils import log_terminal
import invest_rs_engine as rs_engine

IST = pytz.timezone("Asia/Kolkata")

# ── Config (can be overridden from DB) ──────────────────────
RS_PERIOD        = 55       # Primary RS period (days)
RS_ENTRY_MIN     = 1.05     # Sector must be 5% above Nifty to enter
RS_EXIT_BUFFER   = 0.95     # Exit when sector RS drops below this
MAX_SECTORS      = 2        # Max parallel sectors at once
REENTRY_DAYS     = 28       # Min days before re-entering same sector
STOCK_GRACE_DAYS = 14       # Days to hold stock if it's still RS>1.0
STEP_DAYS        = 7        # Backtest step size (weekly)
STOCKS_PER_CAP   = 2        # Top N stocks per cap category


# ════════════════════════════════════════════════════════════
# DATA LAYER — Download all data upfront
# ════════════════════════════════════════════════════════════

def _build_ticker_list() -> list[str]:
    """All tickers needed: Nifty + all sector indices + all stocks."""
    tickers = ["^NSEI"]
    tickers += list(rs_engine.SECTOR_INDICES.values())
    for stock_list in rs_engine.SECTOR_STOCKS.values():
        tickers += [t for t, _ in stock_list]
    return list(set(tickers))


def download_all_data(start_date: date, end_date: date) -> pd.DataFrame:
    """
    Download all historical price data at once (most efficient).
    Returns wide DataFrame: index=date, columns=tickers.
    """
    tickers = _build_ticker_list()
    fetch_start = start_date - timedelta(days=RS_PERIOD + 60)
    fetch_end   = end_date   + timedelta(days=5)

    log_terminal(f"[ROTATION] Downloading {len(tickers)} tickers...", "INFO")
    df = yf.download(
        tickers,
        start=fetch_start.strftime("%Y-%m-%d"),
        end=fetch_end.strftime("%Y-%m-%d"),
        interval="1d",
        progress=False,
        auto_adjust=True,
    )["Close"]

    if isinstance(df, pd.Series):
        df = df.to_frame()

    df.index = pd.to_datetime(df.index).tz_localize(None)
    log_terminal(f"[ROTATION] Downloaded {len(df)} rows × {len(df.columns)} cols.", "INFO")
    return df


def _price_on(df: pd.DataFrame, ticker: str, target_date: pd.Timestamp) -> float | None:
    """Closest available price on or before target_date."""
    if ticker not in df.columns:
        return None
    series = df[ticker].dropna()
    avail  = series[series.index <= target_date]
    if avail.empty:
        return None
    return float(avail.iloc[-1])


def _calc_rs_on(df: pd.DataFrame, ticker: str,
                ref_ticker: str, target_date: pd.Timestamp,
                period: int = RS_PERIOD) -> float | None:
    """RS = (ticker_today/ticker_Nd_ago) / (ref_today/ref_Nd_ago)."""
    old_date = target_date - timedelta(days=period)
    p_now  = _price_on(df, ticker,     target_date)
    p_old  = _price_on(df, ticker,     old_date)
    r_now  = _price_on(df, ref_ticker, target_date)
    r_old  = _price_on(df, ref_ticker, old_date)
    if any(v is None or v == 0 for v in [p_now, p_old, r_now, r_old]):
        return None
    return (p_now / p_old) / (r_now / r_old)


def _calc_rsi_on(df: pd.DataFrame, ticker: str,
                 target_date: pd.Timestamp, period: int = 14) -> float | None:
    """Wilder RSI calculated from historical data up to target_date."""
    if ticker not in df.columns:
        return None
    series = df[ticker].dropna()
    series = series[series.index <= target_date].tail(period * 3)
    if len(series) < period + 5:
        return None
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


# ════════════════════════════════════════════════════════════
# LEGO 1: Market Gate
# ════════════════════════════════════════════════════════════

def get_market_mode_on(df: pd.DataFrame, target_date: pd.Timestamp) -> str:
    """AGGRESSIVE if Nifty RSI > 50, else DEFENSIVE."""
    rsi = _calc_rsi_on(df, "^NSEI", target_date)
    if rsi is None:
        return "AGGRESSIVE"   # default to invest if unknown
    return "AGGRESSIVE" if rsi > 50 else "DEFENSIVE"


# ════════════════════════════════════════════════════════════
# LEGO 2: Sector Scanner (on a specific date)
# ════════════════════════════════════════════════════════════

def scan_sectors_on(df: pd.DataFrame, target_date: pd.Timestamp) -> list[dict]:
    """RS-55 for all sectors on a specific historical date."""
    results = []
    for name, ticker in rs_engine.SECTOR_INDICES.items():
        rs = _calc_rs_on(df, ticker, "^NSEI", target_date)
        if rs is None:
            continue
        results.append({
            "sector":        name,
            "ticker":        ticker,
            "rs":            round(rs, 4),
            "outperforming": rs > 1.0,
        })
    results.sort(key=lambda x: x["rs"], reverse=True)
    for i, r in enumerate(results, 1):
        r["rank"] = i
    return results


# ════════════════════════════════════════════════════════════
# LEGO 3: Leadership Detector
# ════════════════════════════════════════════════════════════

def should_enter_sector(sector_rs: float, sector_rank: int,
                        market_mode: str) -> bool:
    """True if sector qualifies for entry."""
    return (
        market_mode == "AGGRESSIVE" and
        sector_rs >= RS_ENTRY_MIN and
        sector_rank <= 5
    )


def should_exit_sector(sector_rs: float, sector_rank: int) -> bool:
    """True if sector should be exited."""
    return sector_rs < RS_EXIT_BUFFER or sector_rank > 8


# ════════════════════════════════════════════════════════════
# LEGO 4: Stock Picker
# ════════════════════════════════════════════════════════════

def pick_stocks_for_sector(df: pd.DataFrame, sector_name: str,
                            target_date: pd.Timestamp,
                            n_per_cap: int = STOCKS_PER_CAP) -> list[dict]:
    """
    Pick top N stocks per cap category by RS-55.
    Returns list of {symbol, ticker, cap, rs, entry_price}.
    """
    stocks = rs_engine.SECTOR_STOCKS.get(sector_name, [])
    by_cap: dict[str, list] = {"Large": [], "Mid": [], "Small": []}

    for ticker, cap in stocks:
        rs = _calc_rs_on(df, ticker, "^NSEI", target_date)
        if rs is None:
            continue
        price = _price_on(df, ticker, target_date)
        if price is None:
            continue
        by_cap[cap].append({
            "symbol":      ticker.replace(".NS", ""),
            "ticker":      ticker,
            "cap":         cap,
            "rs":          round(rs, 4),
            "entry_price": round(price, 2),
            "entry_date":  target_date.strftime("%Y-%m-%d"),
        })

    # Sort each cap group by RS desc, pick top N
    selected = []
    for cap_name in ["Large", "Mid", "Small"]:
        group = sorted(by_cap[cap_name], key=lambda x: x["rs"], reverse=True)
        selected.extend(group[:n_per_cap])

    return selected


# ════════════════════════════════════════════════════════════
# LEGO 5: Rolling Rotation Backtest Engine
# ════════════════════════════════════════════════════════════

def run_rotation_backtest(
    start_date:    date,
    end_date:      date,
    capital:       float = 100_000,
    max_sectors:   int   = MAX_SECTORS,
    rs_period:     int   = RS_PERIOD,
) -> dict:
    """
    Main backtest function.
    Returns: trade_log, portfolio_curve, summary
    """
    log_terminal(f"[ROTATION] Backtest {start_date} → {end_date} | ₹{capital:,.0f}", "INFO")

    # ── Download all data ──────────────────────────────────
    df = download_all_data(start_date, end_date)

    # ── State tracking ─────────────────────────────────────
    current_capital    = float(capital)
    active_positions   = {}   # sector_name → {entry_date, sector_rs, stocks[]}
    last_exit_dates    = {}   # sector_name → last exit date (for reentry gap)
    stock_grace_ends   = {}   # ticker → date when grace period ends
    trade_log          = []   # List of completed trades
    portfolio_curve    = []   # [{date, capital}] for equity chart

    # Generate weekly date steps
    step_dates = []
    current = start_date
    while current <= end_date:
        step_dates.append(pd.Timestamp(current))
        current += timedelta(days=STEP_DAYS)

    log_terminal(f"[ROTATION] Running {len(step_dates)} weekly steps...", "INFO")

    for step_dt in step_dates:

        # ── 1. Market Gate ──────────────────────────────────
        market_mode = get_market_mode_on(df, step_dt)

        # ── 2. Sector Scan ──────────────────────────────────
        sector_rankings = scan_sectors_on(df, step_dt)
        sector_rs_map   = {s["sector"]: s for s in sector_rankings}

        # ── 3. Check active positions: HOLD or EXIT ─────────
        sectors_to_exit = []
        for sec_name, pos in active_positions.items():
            sec_info = sector_rs_map.get(sec_name)
            if sec_info is None:
                sectors_to_exit.append(sec_name)
                continue

            if should_exit_sector(sec_info["rs"], sec_info["rank"]):
                # HYBRID STOCK EXIT: check each stock RS
                stocks_out = []
                stocks_grace = []
                for st in pos["stocks"]:
                    stock_rs = _calc_rs_on(df, st["ticker"], "^NSEI", step_dt, rs_period)
                    grace_end = stock_grace_ends.get(st["ticker"])

                    if grace_end and step_dt.date() < grace_end:
                        stocks_grace.append(st)   # Still in grace period → hold
                    elif stock_rs and stock_rs > 1.0 and not grace_end:
                        # Stock still strong → give 2-week grace
                        stock_grace_ends[st["ticker"]] = step_dt.date() + timedelta(days=STOCK_GRACE_DAYS)
                        stocks_grace.append(st)
                    else:
                        # Exit stock now
                        exit_price = _price_on(df, st["ticker"], step_dt)
                        if exit_price and st["entry_price"] > 0:
                            st["exit_price"] = round(exit_price, 2)
                            st["exit_date"]  = step_dt.strftime("%Y-%m-%d")
                            st["return_pct"] = round((exit_price / st["entry_price"] - 1) * 100, 2)
                            st["days_held"]  = (step_dt.date() - date.fromisoformat(st["entry_date"])).days
                        stocks_out.append(st)

                # If grace stocks exist AND no stocks forced-exited yet → partial hold
                if stocks_grace and not stocks_out:
                    active_positions[sec_name]["stocks"] = stocks_grace
                    active_positions[sec_name]["grace"] = True
                    continue

                # Full exit: calculate avg return across all stocks
                all_stocks_done = stocks_out.copy()
                for st in stocks_grace:
                    exit_price = _price_on(df, st["ticker"], step_dt)
                    if exit_price and st["entry_price"] > 0:
                        st["exit_price"] = round(exit_price, 2)
                        st["exit_date"]  = step_dt.strftime("%Y-%m-%d")
                        st["return_pct"] = round((exit_price / st["entry_price"] - 1) * 100, 2)
                        st["days_held"]  = (step_dt.date() - date.fromisoformat(st["entry_date"])).days
                        stock_grace_ends.pop(st["ticker"], None)
                    all_stocks_done.append(st)

                valid = [s for s in all_stocks_done if s.get("return_pct") is not None]
                avg_return = np.mean([s["return_pct"] for s in valid]) if valid else 0

                # Nifty return for same period (benchmark)
                nifty_entry = _price_on(df, "^NSEI", pd.Timestamp(pos["entry_date"]))
                nifty_exit  = _price_on(df, "^NSEI", step_dt)
                nifty_ret   = round((nifty_exit / nifty_entry - 1) * 100, 2) if (nifty_entry and nifty_exit) else 0

                capital_before = pos["capital_allocated"]
                capital_after  = capital_before * (1 + avg_return / 100)
                current_capital += (capital_after - capital_before)

                trade_log.append({
                    "trade_id":        len(trade_log) + 1,
                    "sector":          sec_name,
                    "entry_date":      pos["entry_date"],
                    "exit_date":       step_dt.strftime("%Y-%m-%d"),
                    "days_held":       (step_dt.date() - date.fromisoformat(pos["entry_date"])).days,
                    "stocks":          all_stocks_done,
                    "sector_entry_rs": round(pos["entry_rs"], 4),
                    "sector_exit_rs":  round(sec_info["rs"], 4),
                    "portfolio_return_pct": round(avg_return, 2),
                    "capital_before":  round(capital_before, 2),
                    "capital_after":   round(capital_after, 2),
                    "nifty_return_pct": nifty_ret,
                    "beat_nifty":      avg_return > nifty_ret,
                    "exit_reason":     f"RS dropped to {sec_info['rs']:.3f} (< {RS_EXIT_BUFFER})",
                })
                last_exit_dates[sec_name] = step_dt.date()
                sectors_to_exit.append(sec_name)

        for sec_name in sectors_to_exit:
            active_positions.pop(sec_name, None)

        # ── 4. Enter new sectors if capacity available ───────
        if market_mode == "AGGRESSIVE" and len(active_positions) < max_sectors:
            free_slots = max_sectors - len(active_positions)
            capital_per_slot = current_capital / max(max_sectors, 1)

            active_names = set(active_positions.keys())
            candidates   = [
                s for s in sector_rankings
                if s["sector"] not in active_names and
                   should_enter_sector(s["rs"], s["rank"], market_mode) and
                   (step_dt.date() - last_exit_dates.get(s["sector"], date(2000, 1, 1))).days >= REENTRY_DAYS
            ]

            for candidate in candidates[:free_slots]:
                stocks = pick_stocks_for_sector(df, candidate["sector"], step_dt)
                if not stocks:
                    continue

                active_positions[candidate["sector"]] = {
                    "entry_date":        step_dt.strftime("%Y-%m-%d"),
                    "entry_rs":          candidate["rs"],
                    "stocks":            stocks,
                    "capital_allocated": capital_per_slot,
                    "grace":             False,
                }
                log_terminal(
                    f"[ROTATION] ENTER: {candidate['sector']} | "
                    f"RS:{candidate['rs']:.3f} | {len(stocks)} stocks | ₹{capital_per_slot:,.0f}",
                    "INFO"
                )

        # ── 5. Portfolio curve snapshot ──────────────────────
        portfolio_curve.append({
            "date":            step_dt.strftime("%Y-%m-%d"),
            "capital":         round(current_capital, 2),
            "active_sectors":  list(active_positions.keys()),
            "market_mode":     market_mode,
        })

    # ── 6. Force-close any remaining positions at end ───────
    for sec_name, pos in active_positions.items():
        final_dt = pd.Timestamp(end_date)
        all_done = []
        for st in pos["stocks"]:
            exit_price = _price_on(df, st["ticker"], final_dt)
            if exit_price and st["entry_price"] > 0:
                st["exit_price"] = round(exit_price, 2)
                st["exit_date"]  = final_dt.strftime("%Y-%m-%d")
                st["return_pct"] = round((exit_price / st["entry_price"] - 1) * 100, 2)
                st["days_held"]  = (end_date - date.fromisoformat(st["entry_date"])).days
            all_done.append(st)

        valid = [s for s in all_done if s.get("return_pct") is not None]
        avg_return = np.mean([s["return_pct"] for s in valid]) if valid else 0
        capital_before = pos["capital_allocated"]
        capital_after  = capital_before * (1 + avg_return / 100)
        current_capital += (capital_after - capital_before)

        trade_log.append({
            "trade_id":        len(trade_log) + 1,
            "sector":          sec_name,
            "entry_date":      pos["entry_date"],
            "exit_date":       end_date.strftime("%Y-%m-%d"),
            "days_held":       (end_date - date.fromisoformat(pos["entry_date"])).days,
            "stocks":          all_done,
            "sector_entry_rs": round(pos["entry_rs"], 4),
            "sector_exit_rs":  None,
            "portfolio_return_pct": round(avg_return, 2),
            "capital_before":  round(capital_before, 2),
            "capital_after":   round(capital_after, 2),
            "nifty_return_pct": 0,
            "beat_nifty":      avg_return > 0,
            "exit_reason":     "Backtest period ended",
        })

    # ── 7. Summary stats ──────────────────────────────────
    nifty_start = _price_on(df, "^NSEI", pd.Timestamp(start_date))
    nifty_end   = _price_on(df, "^NSEI", pd.Timestamp(end_date))
    nifty_total = round((nifty_end / nifty_start - 1) * 100, 2) if (nifty_start and nifty_end) else 0

    total_return_pct = round((current_capital / capital - 1) * 100, 2)
    profitable_trades = sum(1 for t in trade_log if t["portfolio_return_pct"] > 0)
    win_rate = round(profitable_trades / len(trade_log) * 100, 1) if trade_log else 0

    summary = {
        "start_date":       start_date.strftime("%Y-%m-%d"),
        "end_date":         end_date.strftime("%Y-%m-%d"),
        "total_days":       (end_date - start_date).days,
        "starting_capital": capital,
        "final_capital":    round(current_capital, 2),
        "total_return_pct": total_return_pct,
        "nifty_return_pct": nifty_total,
        "beat_nifty":       total_return_pct > nifty_total,
        "alpha":            round(total_return_pct - nifty_total, 2),
        "total_trades":     len(trade_log),
        "profitable_trades": profitable_trades,
        "win_rate_pct":     win_rate,
        "avg_trade_return": round(np.mean([t["portfolio_return_pct"] for t in trade_log]), 2) if trade_log else 0,
        "best_trade":       max(trade_log, key=lambda t: t["portfolio_return_pct"], default=None),
        "worst_trade":      min(trade_log, key=lambda t: t["portfolio_return_pct"], default=None),
    }

    log_terminal(
        f"[ROTATION] Done | Return: {total_return_pct}% vs Nifty: {nifty_total}% | "
        f"Trades: {len(trade_log)} | Win: {win_rate}%",
        "INFO"
    )
    return {
        "trade_log":       trade_log,
        "portfolio_curve": portfolio_curve,
        "summary":         summary,
    }


# ════════════════════════════════════════════════════════════
# LIVE SCAN (Real-time, not backtest)
# ════════════════════════════════════════════════════════════

def run_live_sector_scan() -> dict:
    """
    Current live RS-55 scan + stock picks for dashboard.
    Returns top sectors + their 2L/2M/2S picks RIGHT NOW.
    """
    today = datetime.now(IST).date()
    start = today - timedelta(days=RS_PERIOD + 90)
    df    = download_all_data(start, today)
    now_dt = pd.Timestamp(today)

    market_mode = get_market_mode_on(df, now_dt)
    sectors     = scan_sectors_on(df, now_dt)

    top_sectors = [
        s for s in sectors
        if s["rs"] >= RS_ENTRY_MIN and s["rank"] <= 5
    ]

    result = {
        "market_mode":   market_mode,
        "nifty_rsi":     _calc_rsi_on(df, "^NSEI", now_dt),
        "scan_date":     today.strftime("%Y-%m-%d"),
        "all_sectors":   sectors,
        "top_sectors":   top_sectors,
        "stock_picks":   {},
    }

    for sec in top_sectors:
        picks = pick_stocks_for_sector(df, sec["sector"], now_dt)
        result["stock_picks"][sec["sector"]] = picks

    # Save to DB
    db.set_param("invest_market_mode",   market_mode)
    db.set_param("invest_nifty_rsi",     str(result["nifty_rsi"] or ""))
    db.set_param("invest_last_scan_dt",  datetime.now(IST).strftime("%Y-%m-%d %H:%M"))
    db.set_param("invest_top_sectors",   json.dumps([s["sector"] for s in top_sectors]))

    return result


if __name__ == "__main__":
    # Quick live scan test
    result = run_live_sector_scan()
    print(f"Mode : {result['market_mode']}")
    print(f"RSI  : {result['nifty_rsi']}")
    print(f"Top  : {[s['sector'] for s in result['top_sectors']]}")
    for sec, picks in result["stock_picks"].items():
        print(f"\n  {sec}:")
        for p in picks:
            print(f"    {p['cap']:6s} {p['symbol']:15s} RS={p['rs']:.3f}")
