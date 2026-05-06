"""
invest_rotation_engine.py — BHARAT ALGOVERSE v4.0 | THE ALPHA HUNTER
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

# ── Config V4.0 "THE ALPHA HUNTER" (Stock Focus — 2026-05-06) ─────
# RULE 1: Nifty gate = 35 (only stop in extreme crash, stay IN the market)
# RULE 2: Individual Stock RSI < 50 = INSTANT SELL (no mercy for weak stocks)
# RULE 3: 2 Large + 2 Mid + 2 Small Cap stocks per sector pick
# RULE 4: Max sectors = 5 (keep capital working, avoid cash)
RS_PERIOD         = 55      # Primary RS period (days)
RS_ENTRY_MIN      = 1.01    # AGGRESSIVE: Enter if even slightly outperforming
RS_ENTRY_FALLBACK = 1.00    # Fallback: keep capital working
RS_EXIT_BUFFER    = 1.00    # EXIT IMMEDIATELY if underperforming Nifty
STOCK_RSI_EXIT    = 50      # Individual stock RSI exit
SECTOR_RSI_EXIT   = 40      # Give sectors more room than stocks
HARD_STOP_LOSS    = -0.15   # -15% max loss per trade
TRAIL_TRIGGER_1   = 0.25    
TRAIL_FLOOR_1     = 0.15    
TRAIL_TRIGGER_2   = 0.45    
TRAIL_FLOOR_2     = 0.30    
NIFTY_RSI_AGGR    = 30      # AGGRESSIVE: Only exit in extreme crash
CONSISTENCY_WEEKS = 0       
MAX_SECTORS       = 3       # Optimized for Alpha vs Diversification
REENTRY_WIN_DAYS  = 7       # Faster re-entry
REENTRY_LOSS_DAYS = 14      
STOCK_GRACE_DAYS  = 0       # No grace, follow the rules
STEP_DAYS         = 7       # Weekly steps
STOCKS_PER_CAP    = 2       # 2 Large + 2 Mid + 2 Small
# Backward compat
REENTRY_DAYS      = REENTRY_WIN_DAYS



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
    """
    V3.4: AGGRESSIVE unless Nifty RSI < 40 (severe crash only).
    Dr. Saab rule: minimize cash time. Only crash = stay out.
    """
    rsi = _calc_rsi_on(df, "^NSEI", target_date)
    if rsi is None:
        return "AGGRESSIVE"    # Unknown = stay in
    if rsi < NIFTY_RSI_AGGR:   # RSI < 40 = true crash, protect capital
        return "DEFENSIVE"
    return "AGGRESSIVE"        # 40-100 = always invest


def _get_sector_rsi(df: pd.DataFrame, sector_name: str,
                    target_date: pd.Timestamp) -> float | None:
    """
    Get the sector index's own RSI(14).
    Dr. Saab rule: if sector RSI < 50 → EXIT immediately.
    """
    import invest_rs_engine as _rs
    sec_ticker = _rs.SECTOR_INDICES.get(sector_name, "")
    if not sec_ticker:
        return None
    return _calc_rsi_on(df, sec_ticker, target_date)



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
    """V4.0: Aggressive entry — stay in the market if it's not a crash."""
    return (
        market_mode == "AGGRESSIVE" and
        sector_rs >= RS_ENTRY_MIN and   # 1.05
        sector_rank <= 7                # Slightly wider rank allowance
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
    V4.0: Mandatory RSI > 50 check for entry.
    """
    stocks = rs_engine.SECTOR_STOCKS.get(sector_name, [])
    by_cap: dict[str, list] = {"Large": [], "Mid": [], "Small": []}

    for ticker, cap in stocks:
        rs = _calc_rs_on(df, ticker, "^NSEI", target_date)
        if rs is None:
            continue
        
        # V4.0: Check RSI before entry
        rsi = _calc_rsi_on(df, ticker, target_date)
        if rsi is None or rsi < 50: # Don't enter weak stocks
            continue

        price = _price_on(df, ticker, target_date)
        if price is None:
            continue
            
        by_cap[cap].append({
            "symbol":      ticker.replace(".NS", ""),
            "ticker":      ticker,
            "cap":         cap,
            "rs":          round(rs, 4),
            "rsi":         round(rsi, 2),
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

    # ── State tracking (V2 extended) ───────────────────────
    current_capital    = float(capital)
    active_positions   = {}   # sector_name → {entry_date, sector_rs, stocks[], trail_floor}
    last_exit_dates    = {}   # sector_name → last exit date (for reentry gap)
    last_exit_profits  = {}   # V2: sector_name → True if last trade was profitable
    _gap_overrides     = {}   # V2: sector_name → actual gap to use (28 or 56)
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

        # ── 3. Check active positions: HOLD, STOCK-EXIT, or SECTOR-EXIT ──
        sectors_to_exit = []
        for sec_name, pos in active_positions.items():
            sec_info = sector_rs_map.get(sec_name)
            if sec_info is None:
                sectors_to_exit.append(sec_name)
                continue

            # ── V4.0: Individual Stock RSI Management ──────────
            remaining_stocks = []
            exited_stocks = []
            
            for st in pos["stocks"]:
                cur_px = _price_on(df, st["ticker"], step_dt)
                if not cur_px:
                    remaining_stocks.append(st)
                    continue

                stock_rsi = _calc_rsi_on(df, st["ticker"], step_dt)
                
                # Dr. Saab Rule: Stock RSI < 50 = INSTANT EXIT
                if stock_rsi is not None and stock_rsi < STOCK_RSI_EXIT:
                    st["exit_price"] = round(cur_px, 2)
                    st["exit_date"]  = step_dt.strftime("%Y-%m-%d")
                    st["return_pct"] = round((cur_px / st["entry_price"] - 1) * 100, 2)
                    st["days_held"]  = (step_dt.date() - date.fromisoformat(st["entry_date"])).days
                    st["exit_reason"] = f"Stock RSI {stock_rsi:.1f} < {STOCK_RSI_EXIT}"
                    exited_stocks.append(st)
                else:
                    remaining_stocks.append(st)

            # Update capital based on exited stocks
            if exited_stocks:
                for est in exited_stocks:
                    portion_capital = (pos["capital_allocated"] / (STOCKS_PER_CAP * 3)) # assuming balanced weight
                    realized_val = portion_capital * (1 + est["return_pct"] / 100)
                    current_capital += (realized_val - portion_capital)
                    # Deduct from pos allocation to keep it consistent
                    pos["capital_allocated"] -= portion_capital
                
                pos["stocks"] = remaining_stocks
                log_terminal(f"[ALPHA-V4] STOCK-EXIT: {len(exited_stocks)} stocks from {sec_name} (RSI < 50)", "INFO")

            # ── Sector-level checks ────────────────────────────
            # Calculate current avg return of the position (for remaining)
            all_returns = [st.get("return_pct", 0) for st in exited_stocks]
            for st in remaining_stocks:
                cur_px = _price_on(df, st["ticker"], step_dt)
                if cur_px and st["entry_price"] > 0:
                    all_returns.append(((cur_px / st["entry_price"]) - 1) * 100)
            
            avg_cur_return_pct = float(np.mean(all_returns)) if all_returns else 0
            avg_cur_return = avg_cur_return_pct / 100

            hard_stop_triggered = avg_cur_return <= HARD_STOP_LOSS
            
            trail_stop_triggered = False
            trail_floor = pos.get("trail_floor", None)
            if trail_floor is not None and avg_cur_return < trail_floor:
                trail_stop_triggered = True
            
            if avg_cur_return >= TRAIL_TRIGGER_2 and pos.get("trail_floor", 0) < TRAIL_FLOOR_2:
                active_positions[sec_name]["trail_floor"] = TRAIL_FLOOR_2
            elif avg_cur_return >= TRAIL_TRIGGER_1 and pos.get("trail_floor") is None:
                active_positions[sec_name]["trail_floor"] = TRAIL_FLOOR_1

            sec_rsi = _get_sector_rsi(df, sec_name, step_dt)
            sector_rsi_exit = (sec_rsi is not None and sec_rsi < SECTOR_RSI_EXIT)

            # Sector Exit Trigger
            exit_triggered = (
                hard_stop_triggered or
                trail_stop_triggered or
                sector_rsi_exit or
                should_exit_sector(sec_info["rs"], sec_info["rank"]) or
                not pos["stocks"] # If all stocks exited, close sector pos
            )

            if exit_triggered:
                _hard = hard_stop_triggered
                _trail = trail_stop_triggered
                _srsi = sector_rsi_exit
                exit_reason = (
                    f"HARD STOP: {avg_cur_return*100:.1f}%" if _hard else
                    f"SECTOR RSI {sec_rsi:.0f}" if _srsi else
                    f"TRAIL STOP" if _trail else
                    f"RS exit: {sec_info['rs']:.3f}" if pos["stocks"] else
                    "ALL STOCKS EXITED (RSI < 50)"
                )

                # Process final exit for remaining stocks
                final_exits = exited_stocks.copy()
                for st in pos["stocks"]:
                    exit_price = _price_on(df, st["ticker"], step_dt)
                    if exit_price and st["entry_price"] > 0:
                        st["exit_price"] = round(exit_price, 2)
                        st["exit_date"]  = step_dt.strftime("%Y-%m-%d")
                        st["return_pct"] = round((exit_price / st["entry_price"] - 1) * 100, 2)
                        st["days_held"]  = (step_dt.date() - date.fromisoformat(st["entry_date"])).days
                    final_exits.append(st)

                # Calculate final realization for the sector
                sector_final_return = np.mean([s["return_pct"] for s in final_exits]) if final_exits else 0
                
                # Realize remaining capital if any
                if pos["stocks"]:
                    remaining_cap = pos["capital_allocated"]
                    final_val = remaining_cap * (1 + (np.mean([s["return_pct"] for s in final_exits if s in pos["stocks"]]) / 100))
                    current_capital += (final_val - remaining_cap)

                trade_log.append({
                    "trade_id":             len(trade_log) + 1,
                    "sector":               sec_name,
                    "entry_date":           pos["entry_date"],
                    "exit_date":            step_dt.strftime("%Y-%m-%d"),
                    "days_held":            (step_dt.date() - date.fromisoformat(pos["entry_date"])).days,
                    "stocks":               final_exits,
                    "portfolio_return_pct": round(sector_final_return, 2),
                    "capital_before":       round(pos["capital_allocated"], 2),
                    "capital_after":        round(pos["capital_allocated"] * (1 + sector_final_return / 100), 2),
                    "nifty_return_pct":     0, # Will be filled later or handled by UI
                    "beat_nifty":           sector_final_return > 0,
                    "exit_reason":          exit_reason,
                    "hard_stop":            hard_stop_triggered,
                })
                
                was_winner = sector_final_return > 0
                reentry_gap = REENTRY_LOSS_DAYS if not was_winner else REENTRY_WIN_DAYS
                last_exit_dates[sec_name] = step_dt.date()
                _gap_overrides[sec_name] = reentry_gap
                sectors_to_exit.append(sec_name)

        for sec_name in sectors_to_exit:
            active_positions.pop(sec_name, None)

        # ── 4. Enter new sectors (Dr. Saab: ALWAYS be in market!) ──
        # Priority 1: RS > 1.05 (strong leaders)
        # Priority 2: RS > 1.0 (fallback — never sit in cash unnecessarily)
        if market_mode == "AGGRESSIVE" and len(active_positions) < max_sectors:
            free_slots       = max_sectors - len(active_positions)
            capital_per_slot = current_capital / max(max_sectors, 1)
            active_names     = set(active_positions.keys())

            def _eligible(s, min_rs):
                if s["sector"] in active_names:
                    return False
                gap_needed = _gap_overrides.get(s["sector"], REENTRY_WIN_DAYS)
                days_since = (step_dt.date() - last_exit_dates.get(s["sector"], date(2000, 1, 1))).days
                if days_since < gap_needed:
                    return False
                if s["rs"] < min_rs or s["rank"] > 7:
                    return False
                # Quick sector RSI check — don't enter a sector already weakening
                _srsi = _get_sector_rsi(df, s["sector"], step_dt)
                if _srsi is not None and _srsi < SECTOR_RSI_EXIT:
                    return False
                return True

            # Priority 1: strong RS > 1.05
            candidates = [s for s in sector_rankings if _eligible(s, RS_ENTRY_MIN)]

            # Fallback: if still have free slots, take best RS > 1.0
            # (Dr. Saab: never stay in cash — find something running)
            if len(candidates) < free_slots:
                fallback = [s for s in sector_rankings
                            if _eligible(s, RS_ENTRY_FALLBACK)
                            and s not in candidates]
                candidates += fallback

            for candidate in (candidates[:free_slots]):
                stocks = pick_stocks_for_sector(df, candidate["sector"], step_dt)
                if not stocks:
                    continue
                active_positions[candidate["sector"]] = {
                    "entry_date":        step_dt.strftime("%Y-%m-%d"),
                    "entry_rs":          candidate["rs"],
                    "stocks":            stocks,
                    "capital_allocated": capital_per_slot,
                    "grace":             False,
                    "trail_floor":       None,
                }
                tag = "STRONG" if candidate["rs"] >= RS_ENTRY_MIN else "FALLBACK"
                log_terminal(
                    f"[V4.0 {tag}] ENTER: {candidate['sector']} RS:{candidate['rs']:.3f}",
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


def run_pure_stock_scan(top_n: int = 15) -> list[dict]:
    """
    V5.0: Direct stock momentum scan across ALL sectors.
    Returns top N stocks by RS-55, filtered by RSI > 50.
    """
    from datetime import datetime, timedelta
    today = datetime.now(IST).date()
    start = today - timedelta(days=RS_PERIOD + 90)
    df    = download_all_data(start, today)
    now_dt = pd.Timestamp(today)

    all_stocks = []
    for sec_name, stocks in rs_engine.SECTOR_STOCKS.items():
        for ticker, cap in stocks:
            rs = _calc_rs_on(df, ticker, "^NSEI", now_dt)
            rsi = _calc_rsi_on(df, ticker, now_dt)
            
            if rs is not None:
                all_stocks.append({
                    "symbol": ticker.replace(".NS", ""),
                    "ticker": ticker,
                    "sector": sec_name,
                    "cap":    cap,
                    "rs":     round(rs, 4),
                    "rsi":    rsi,
                    "price":  _price_on(df, ticker, now_dt)
                })

    # Filter by RSI and sort by RS
    candidates = [s for s in all_stocks if s["rsi"] is not None and s["rsi"] >= 50]
    candidates.sort(key=lambda x: x["rs"], reverse=True)

    return candidates[:top_n]


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
