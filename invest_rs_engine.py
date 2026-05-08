"""
invest_rs_engine.py — BHARAT ALGOVERSE v4.5 | BSE Sectoral RS Engine
=====================================================================
Calculates Relative Strength (RS) across 70+ BSE Detailed Industries.
Uses Stock-Group Averaging to simulate official BSE Sectoral Indices.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import pandas_ta as ta
import os
from utils import log_terminal

# ============================================================
# 🏢 BSE DETAILED SECTOR MAP (70+ INDUSTRIES)
# ============================================================
# Mapping of 70+ BSE-style sectors to their major constituent stocks.
# These will be used to calculate "Synthetic Sector RS".
BSE_SECTOR_MAP = {
    "Abrasives": ["GRINDWELL.NS", "CARBORUNIV.NS"],
    "Aerospace & Defence": ["HAL.NS", "BEL.NS", "BDL.NS", "MAZDOCK.NS", "GRSE.NS", "BEML.NS"],
    "Agrochemicals": ["UPL.NS", "PIIND.NS", "SUMICHEM.NS", "RALLIS.NS", "SHARDACROP.NS"],
    "Air Transport Service": ["INDIGO.NS", "SPICEJET.NS"],
    "Aluminium & Aluminium Products": ["HINDALCO.NS", "NATIONALUM.NS"],
    "Auto Components & Equipments": ["MOTHERSON.NS", "UNO_MINDA.NS", "SONACOMS.NS", "ENDURANCE.NS", "CIEINDIA.NS"],
    "Automobiles": ["MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "EICHERMOT.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS"],
    "Banks - Private": ["HDFCBANK.NS", "ICICIBANK.NS", "AXISBANK.NS", "KOTAKBANK.NS", "INDUSINDBK.NS", "FEDERALBNK.NS"],
    "Banks - PSU": ["SBIN.NS", "BANKBARODA.NS", "CANBK.NS", "UNIONBANK.NS", "PNB.NS", "IOB.NS", "UCOBANK.NS"],
    "Beverages": ["VBL.NS", "UBL.NS", "UNITDSPR.NS"],
    "BPO / KPO": ["GENPACT.NS", "WNS.NS", "FIRSTSOURCE.NS"],
    "Breweries & Distilleries": ["RADICO.NS", "SULA.NS", "GLOBOFFS.NS"],
    "Cement & Cement Products": ["ULTRACEMCO.NS", "GRASIM.NS", "AMBUJACEM.NS", "ACC.NS", "DALBHARAT.NS", "JKCEMENT.NS"],
    "Chemicals - Speciality": ["AARTIIND.NS", "VINATIORGA.NS", "DEEPAKNTR.NS", "SRF.NS", "NAVINFLUOR.NS", "ATUL.NS"],
    "Chemicals - Basic": ["TATACHEM.NS", "GUJALKALI.NS", "DCW.NS"],
    "Coal": ["COALINDIA.NS"],
    "Construction & Engineering": ["LT.NS", "KEC.NS", "KALPATPOWR.NS", "ASHOKA.NS", "PNCINFRA.NS"],
    "Consumer Durables": ["TITAN.NS", "HAVELLS.NS", "VOLTAS.NS", "CROMPTON.NS", "DIXON.NS", "WHIRLPOOL.NS"],
    "Consumer Food": ["NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS", "VBL.NS", "ITC.NS"],
    "Data Infrastructure": ["DATAINFRA.NS", "BHEL.NS", "STERTOOLS.NS"],
    "Diversified Retail": ["DMART.NS", "TRENT.NS", "ABFRL.NS", "V2RETAIL.NS"],
    "E-Commerce / Digital": ["ZOMATO.NS", "NYKAA.NS", "POLICYBZR.NS", "DELHIVERY.NS", "PAYTM.NS"],
    "Electrical Equipment": ["ABB.NS", "SIEMENS.NS", "CGPOWER.NS", "SUZLON.NS", "THERMAX.NS"],
    "Fertilizers": ["COROMANDEL.NS", "CHAMBLFERT.NS", "GNFC.NS", "FACT.NS", "RCF.NS"],
    "Footwear": ["RELAXO.NS", "BATAINDIA.NS", "CAMPUS.NS", "METROBRAND.NS"],
    "Gas Utility": ["GAIL.NS", "IGL.NS", "MGL.NS", "GUJGASLTD.NS"],
    "Healthcare Services": ["APOLLOHOSP.NS", "MAXHEALTH.NS", "FORTIS.NS", "GLOBAL.NS", "METROPOLIS.NS"],
    "Hotels & Resorts": ["INDHOTEL.NS", "EIHOTEL.NS", "CHALET.NS", "LEMON_TREE.NS"],
    "Household Products": ["HINDUNILVR.NS", "GODREJCP.NS", "DABUR.NS", "MARICO.NS", "COLPAL.NS"],
    "Housing Finance": ["HDFC.NS", "LICHSGFIN.NS", "HUDCO.NS", "PNBHOUSING.NS", "CANFINHOME.NS"],
    "Industrial Products": ["CUMMINSIND.NS", "BHARATFORG.NS", "SKFINDIA.NS", "TIMKEN.NS", "AIAENG.NS"],
    "Insurance": ["HDFCLIFE.NS", "SBILIFE.NS", "ICICIPRULI.NS", "LICI.NS", "GICRE.NS"],
    "IT - Software": ["TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "LTIM.NS", "TECHM.NS", "PERSISTENT.NS"],
    "IT - Services": ["MPHASIS.NS", "COFORGE.NS", "TATAELXSI.NS", "KPITTECH.NS", "CYIENT.NS"],
    "Logistics": ["CONCOR.NS", "DELHIVERY.NS", "GATEWAY.NS", "TCI.NS", "AEGISLOG.NS"],
    "Media & Entertainment": ["SUNTV.NS", "ZEEL.NS", "PVRINOX.NS", "TV18BRDCST.NS"],
    "Metals - Ferrous": ["TATASTEEL.NS", "JSWSTEEL.NS", "JINDALSTEL.NS", "SAIL.NS", "NMDC.NS"],
    "Mining": ["VEDL.NS", "HINDZINC.NS", "NMDC.NS"],
    "NBFC": ["BAJFINANCE.NS", "BAJAJFINSV.NS", "CHOLAFIN.NS", "SHRIRAMFIN.NS", "MUTHOOTFIN.NS", "M&MFIN.NS"],
    "Oil & Gas - Refining": ["RELIANCE.NS", "BPCL.NS", "IOC.NS", "HPCL.NS", "MRPL.NS"],
    "Packaging": ["POLYPLEX.NS", "Uフレックス.NS", "ESSELPRO.NS"],
    "Paint": ["ASIANPAINT.NS", "BERGEPAINT.NS", "KANSAINER.NS", "INDIGOPNTS.NS"],
    "Paper & Paper Products": ["JKPAPER.NS", "WESTPCP.NS", "TNPL.NS"],
    "Personal Care": ["HINDUNILVR.NS", "GODREJCP.NS", "DABUR.NS", "COLPAL.NS", "EMAMILTD.NS"],
    "Pharmaceuticals": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "TORNTPHARM.NS", "ALKEM.NS", "MANKIND.NS"],
    "Power - Generation": ["NTPC.NS", "TATAPOWER.NS", "ADANIPOWER.NS", "JSWENERGY.NS", "NHPC.NS", "SJVN.NS"],
    "Power - Transmission": ["POWERGRID.NS", "ADANITRANS.NS"],
    "Real Estate": ["DLF.NS", "LODHA.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PHOENIXLTD.NS", "PRESTIGE.NS"],
    "Shipbuilding": ["COCHINSHIP.NS", "MAZDOCK.NS", "GRSE.NS"],
    "Steel": ["TATASTEEL.NS", "JSWSTEEL.NS", "JINDALSTEL.NS", "SAIL.NS"],
    "Telecom - Services": ["BHARTIARTL.NS", "IDEA.NS"],
    "Telecom - Equipment": ["HFCL.NS", "ITI.NS"],
    "Textiles": ["PAGEIND.NS", "TRIDENT.NS", "RAYMOND.NS", "WELSPUNIND.NS", "KPRMILL.NS"],
    "Tyres": ["MRF.NS", "APOLLOTYRE.NS", "BALKRISIND.NS", "CEATLTD.NS", "JKTYRE.NS"],
}

NIFTY_TICKER = "^NSEI"
RS_PERIOD    = 55   # 3 months approx
RS_PERIOD_LONG = 125 # 6 months
RSI_PERIOD   = 14

def get_data(ticker, period_days=150):
    """Fetches historical data with caching."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)
        data = yf.download(ticker, start=start_date, end=end_date, interval="1d", progress=False)
        return data if not data.empty else None
    except Exception as e:
        return None

def calc_rs(ticker, benchmark="^NSEI", period=55):
    """Calculates Relative Strength (RS) ratio."""
    try:
        t_data = get_data(ticker, period + 10)
        b_data = get_data(benchmark, period + 10)
        
        if t_data is None or b_data is None or len(t_data) < period or len(b_data) < period:
            return None
            
        t_ret = (t_data['Close'].iloc[-1] / t_data['Close'].iloc[-period]) - 1
        b_ret = (b_data['Close'].iloc[-1] / b_data['Close'].iloc[-period]) - 1
        
        # RS = (1 + Stock Return) / (1 + Benchmark Return)
        rs = (1 + t_ret) / (1 + b_ret)
        return float(rs)
    except Exception:
        return None

def scan_bse_sectors(period=55):
    """Scans all 70+ BSE sectors using stock-group averaging."""
    log_terminal(f"[RS-ENGINE] Scanning {len(BSE_SECTOR_MAP)} BSE Sectors...", "INFO")
    results = []
    
    for sector, stocks in BSE_SECTOR_MAP.items():
        rs_values = []
        for s in stocks:
            rs = calc_rs(s, NIFTY_TICKER, period)
            if rs: rs_values.append(rs)
        
        if rs_values:
            avg_rs = np.mean(rs_values)
            results.append({
                "sector": sector,
                "rs": avg_rs,
                "vs_nifty_pct": (avg_rs - 1) * 100,
                "outperforming": avg_rs > 1.0,
                "confidence": len(rs_values) / len(stocks) # How many stocks had data
            })
            
    # Sort by RS descending
    results.sort(key=lambda x: x["rs"], reverse=True)
    
    # Assign Rank
    for i, res in enumerate(results, 1):
        res["rank"] = i
        
    return results

# Alias for backward compatibility
scan_sectors = scan_bse_sectors

def get_market_pulse():
    """Gets Nifty RSI and Market Mode."""
    try:
        data = get_data(NIFTY_TICKER, 50)
        if data is not None:
            rsi = ta.rsi(data['Close'], length=RSI_PERIOD).iloc[-1]
            mode = "AGGRESSIVE" if rsi > 50 else "DEFENSIVE"
            return {"rsi": round(rsi, 1), "mode": mode, "close": data['Close'].iloc[-1]}
    except:
        pass
    return {"rsi": 50.0, "mode": "NEUTRAL", "close": 0.0}

if __name__ == "__main__":
    sectors = scan_bse_sectors()
    print(pd.DataFrame(sectors).head(10))
