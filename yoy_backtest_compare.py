"""
yoy_backtest_compare.py — Year-on-Year Backtest
RS Rotation Strategy vs Nifty 50 vs Nifty Next 50 (Alpha proxy)

Uses only confirmed yfinance tickers for Indian market.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import io, codecs
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date
import warnings
warnings.filterwarnings("ignore")

try:
    from invest_rotation_engine import run_rotation_backtest
    HAS_ENGINE = True
except Exception as e:
    print(f"[WARN] Engine: {e}")
    HAS_ENGINE = False

CAPITAL     = 100_000
MAX_SECTORS = 3

YEARS = [
    (date(2021, 1,  1), date(2021, 12, 31), "2021"),
    (date(2022, 1,  1), date(2022, 12, 31), "2022"),
    (date(2023, 1,  1), date(2023, 12, 31), "2023"),
    (date(2024, 1,  1), date(2024, 12, 31), "2024"),
    (date(2025, 1,  1), date(2025, 12, 31), "2025"),
    (date(2026, 1,  1), date(2026,  5,  6), "2026 YTD"),
]

# Confirmed working NSE tickers on yfinance
BENCHMARKS = {
    "Nifty 50":        "^NSEI",
    "Nifty Next 50":   "^NSMIDCP",    # Nifty Midcap Select — good alpha proxy
    "Nifty 500":       "^CRSLDX",     # Broad India market
    "Nifty Smallcap":  "^CNXSC",
}

print("\nDownloading benchmark data...")
bench_dfs = {}
for bname, bticker in BENCHMARKS.items():
    try:
        df = yf.download(bticker, start=date(2021,1,1), end=date(2026,5,8),
                         auto_adjust=True, progress=False)
        if not df.empty:
            bench_dfs[bname] = df
            print(f"  OK: {bname} ({bticker}) — {len(df)} rows")
        else:
            print(f"  SKIP: {bname} — empty")
    except Exception as ex:
        print(f"  FAIL: {bname} — {ex}")

def period_ret(df, s, e):
    if df is None or df.empty:
        return None
    try:
        sub = df.loc[str(s):str(e)]["Close"]
        if hasattr(sub.columns if hasattr(sub,'columns') else None, '__len__'):
            sub = sub.iloc[:,0]
        sub = sub.dropna()
        if len(sub) < 2:
            return None
        return round((float(sub.iloc[-1]) / float(sub.iloc[0]) - 1) * 100, 2)
    except:
        return None

print("\nRunning RS Rotation backtest 2021-2026 (takes 5-10 min)...")
full_log, full_curve, full_summary = [], [], {}
if HAS_ENGINE:
    try:
        full_log, full_curve, full_summary = run_rotation_backtest(
            date(2021, 1, 1), date(2026, 5, 6), CAPITAL, max_sectors=MAX_SECTORS
        )
        print(f"  Backtest done: {len(full_log)} trades")
    except Exception as e:
        print(f"  Backtest error: {e}")
        HAS_ENGINE = False

def strat_yoy(curve, s, e):
    if not curve:
        return None
    try:
        if isinstance(curve, pd.DataFrame):
            dfp = curve.copy()
        elif isinstance(curve, list):
            dfp = pd.DataFrame(list(curve))
        else:
            return None
        if dfp.empty or "capital" not in dfp.columns:
            return None
        dfp["date"] = pd.to_datetime(dfp["date"])
        dfp = dfp.set_index("date").sort_index()
        sub = dfp.loc[str(s):str(e)]
        if sub.empty:
            return None
        c0, c1 = float(sub["capital"].iloc[0]), float(sub["capital"].iloc[-1])
        return round((c1/c0 - 1) * 100, 2)
    except Exception as ex:
        print(f"  strat_yoy error: {ex}")
        return None

# ── Print table ───────────────────────────────────────────
print()
print("=" * 100)
print("  YEAR-BY-YEAR: RS Rotation v3.4  vs  Nifty Benchmarks")
print("=" * 100)

headers = ["Year", "RS Strategy"] + list(bench_dfs.keys())
widths  = [12, 14] + [14]*len(bench_dfs)

header_line = "  " + "".join(h.ljust(w) for h, w in zip(headers, widths))
print(header_line)
print("  " + "-"*96)

all_strat, all_nifty = [], []
beat_n = 0
total_y = 0

for (y_s, y_e, label) in YEARS:
    s_ret  = strat_yoy(full_curve, y_s, y_e)
    b_rets = {bn: period_ret(bd, y_s, y_e) for bn, bd in bench_dfs.items()}
    nifty_r = b_rets.get("Nifty 50")

    s_str = f"{s_ret:+.1f}%" if s_ret is not None else " N/A"
    cols = [label, s_str]
    for bn in bench_dfs:
        r = b_rets.get(bn)
        marker = ""
        if r is not None and s_ret is not None:
            marker = " [+]" if s_ret > r else " [-]"
        cols.append(f"{r:+.1f}%{marker}" if r is not None else " N/A")

    print("  " + "".join(c.ljust(w) for c, w in zip(cols, widths)))
    if s_ret: all_strat.append(s_ret)
    if nifty_r: all_nifty.append(nifty_r)
    if s_ret and nifty_r:
        total_y += 1
        if s_ret > nifty_r: beat_n += 1

# Compound totals
def compound(rets):
    v = CAPITAL
    for r in rets: v *= (1 + r/100)
    return v

final_s = compound(all_strat)
final_n = compound(all_nifty)

print("  " + "-"*96)
print(f"  {'COMPOUND':12} {'Rs '+str(round(final_s)):14}", end="")
for bn, bd in bench_dfs.items():
    all_b = [period_ret(bd, ys, ye) for (ys,ye,_) in YEARS]
    all_b = [r for r in all_b if r]
    fc = compound(all_b)
    pct = (fc/CAPITAL - 1)*100
    print(f" Rs{fc:,.0f} ({pct:+.1f}%)".ljust(14), end="")
print()
print(f"\n  Strategy final: Rs {final_s:,.0f}  ({(final_s/CAPITAL-1)*100:+.1f}%)")
print(f"  Nifty final:    Rs {final_n:,.0f}  ({(final_n/CAPITAL-1)*100:+.1f}%)")
print(f"  Beat Nifty in {beat_n}/{total_y} years")

# Trade stats
if full_log:
    rets  = [t.get("portfolio_return_pct",0) for t in full_log]
    wins  = sum(1 for r in rets if r > 0)
    hstop = sum(1 for t in full_log if t.get("hard_stop"))
    rsie  = sum(1 for t in full_log if "SECTOR RSI" in t.get("exit_reason",""))
    print(f"\n  TRADE STATS: {len(full_log)} trades | {wins} wins ({wins/max(len(full_log),1)*100:.0f}% win rate)")
    print(f"  Avg return: {np.mean(rets):+.2f}% | Best: {max(rets):+.1f}% | Worst: {min(rets):+.1f}%")
    print(f"  Hard stops hit: {hstop} | Sector RSI exits: {rsie}")

print("=" * 100)
print()
