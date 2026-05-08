"""
invest_rotation_engine.py — BHARAT ALGOVERSE v4.5 | THE BSE ALPHA HUNTER
===========================================================================
Rolling Sector Rotation Engine using 70+ BSE Detailed Industries.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
import pytz
import json
import db
from utils import log_terminal
import invest_rs_engine as rs_engine

IST = pytz.timezone("Asia/Kolkata")

def run_live_sector_scan() -> dict:
    """
    Performs a live scan of all 70+ BSE sectors.
    """
    log_terminal("[ROTATION] Running Live BSE Sectoral Scan...", "INFO")
    
    # 1. Market Mode
    pulse = rs_engine.get_market_pulse()
    
    # 2. Sector RS Scan
    sectors = rs_engine.scan_bse_sectors(rs_engine.RS_PERIOD)
    
    # 3. Top Sectors (RS > 1.0)
    top_sectors = [s for s in sectors if s["rs"] > 1.05 and s["rank"] <= 15]
    
    # 4. Stock Picks (Top 3 stocks for top 5 sectors)
    stock_picks = {}
    for sec in top_sectors[:10]:
        sec_name = sec["sector"]
        stocks = rs_engine.BSE_SECTOR_MAP.get(sec_name, [])
        picks = []
        for s in stocks:
            rs = rs_engine.calc_rs(s, rs_engine.NIFTY_TICKER, rs_engine.RS_PERIOD)
            if rs:
                picks.append({
                    "symbol": s.replace(".NS", ""),
                    "ticker": s,
                    "rs": round(rs, 4)
                })
        picks.sort(key=lambda x: x["rs"], reverse=True)
        stock_picks[sec_name] = picks[:3]
        
    result = {
        "market_mode": pulse["mode"],
        "nifty_rsi": pulse["rsi"],
        "scan_date": datetime.now(IST).strftime("%Y-%m-%d"),
        "all_sectors": sectors,
        "top_sectors": top_sectors,
        "stock_picks": stock_picks
    }
    
    # Save to DB for dashboard
    db.set_param("invest_market_mode", result["market_mode"])
    db.set_param("invest_nifty_rsi", str(result["nifty_rsi"]))
    db.set_param("invest_last_scan_dt", datetime.now(IST).strftime("%Y-%m-%d %H:%M"))
    db.set_param("invest_top_sectors", json.dumps([s["sector"] for s in top_sectors[:5]]))
    
    return result

if __name__ == "__main__":
    res = run_live_sector_scan()
    print(f"Top 5 Sectors: {[s['sector'] for s in res['top_sectors'][:5]]}")
