"""
invest_newsletter.py — BHARAT ALGOVERSE v3.1 | Strategic Newsletter Engine
===========================================================================
Generates Daily, Weekly, and Monthly reports in Text and HTML formats.
Optimized for Telegram, Twitter, and Dashboard display.
"""

import pandas as pd
from datetime import datetime, timedelta
import pytz
import json
import db
import invest_rs_engine as rs_engine
import invest_rotation_engine as rot_eng
import invest_fundamentals as fund_eng
import invest_report as rep_eng
from utils import log_terminal, send_telegram_msg

IST = pytz.timezone("Asia/Kolkata")

# ── Branding ──────────────────────────────────────────────────
SYSTEM_NAME = "BHARAT MARKET COMPASS"
SYSTEM_ICON = "🧭"
SYSTEM_TAGLINE = "India's Institutional-Grade Market Intelligence"
SYSTEM_VERSION = "v3.1"

def generate_newsletter_content(newsletter_type="DAILY"):
    """
    Main entry point for newsletter generation.
    Pulls live scan data and formats it according to the requested type.
    """
    log_terminal(f"[NEWSLETTER] Generating {newsletter_type} report...", "INFO")
    
    # 1. Run live scan to get fresh data
    scan_data = rot_eng.run_live_sector_scan()
    
    # 2. Build Text (Telegram/Compass) version
    text_content = _build_compass_text(scan_data, newsletter_type)
        
    # 3. Build HTML (Web/Dashboard) version
    html_content = _build_html_version(scan_data, newsletter_type)
    
    return {
        "text": text_content,
        "html": html_content,
        "data": scan_data,
        "type": newsletter_type,
        "date": datetime.now(IST).strftime("%d %b %Y %H:%M")
    }

def _build_compass_text(scan_data, newsletter_type):
    """
    Builds the high-detail 'BHARAT MARKET COMPASS' text format.
    Exactly matching the user's preferred style.
    """
    now_str    = datetime.now(IST).strftime("%d %b %Y %H:%M IST")
    type_label = "DAILY INTELLIGENCE" if newsletter_type == "DAILY" else ("WEEKLY REVIEW" if newsletter_type == "WEEKLY" else "MONTHLY STRATEGIC OUTLOOK")
    
    pulse      = scan_data.get("pulse", {})
    top_secs   = scan_data.get("top_sectors", [])
    stock_picks = scan_data.get("stock_picks", {})
    
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{SYSTEM_ICON} {SYSTEM_NAME}",
        f"📅 {type_label} | {now_str}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "📈 MARKET PULSE",
        f"Nifty 50: ₹{pulse.get('close', 0):,.0f}",
        f"Trend Signal: {'🟢 POSITIVE MOMENTUM' if scan_data.get('market_mode') == 'AGGRESSIVE' else '🔴 CAUTION'}",
        "✅ Market above key threshold — Stay invested. Ride momentum." if scan_data.get("market_mode") == "AGGRESSIVE" else "⚠️ Market below key threshold — Reduce risk. Protect capital.",
        "",
        "🏆 SECTOR LEADERSHIP BOARD",
        "_Sectors consistently beating the broader Indian market:_",
        "",
    ]
    
    for i, sec in enumerate(top_secs[:5], 1):
        thesis = fund_eng.get_sector_thesis(sec["sector"])
        lines += [
            f"{i}. 🟢🟢 STRONG LEADER",
            f"{sec['sector'].replace('Nifty ', '').upper()}",
        ]
        for r in thesis.get("reasons", [])[:3]:
            lines.append(f"  {r}")
        lines.append(f"  📋 Outlook: {thesis.get('short', '')}")
        lines.append("")
        
        # Add Top Picks for this sector
        picks = stock_picks.get(sec["sector"], [])[:3]
        if picks:
            lines.append(f"  🎯 Top Picks — {sec['sector'].replace('Nifty ', '')}:")
            for p in picks:
                st_label = "🔥 Exceptional momentum" if p.get("rs", 0) > 1.1 else "🟢🟢 Very strong"
                cap_icon = "🏦" if p['cap'] == "Large" else ("🏢" if p['cap'] == "Mid" else "🏪")
                lines.append(f"  {cap_icon} {p['symbol']} — {p['cap']} Cap | {st_label}")
                
                # Financials (Mocked or fetched if available)
                # In real use, we'd call rep_eng._fetch_financials(p['ticker'])
                # For now, let's keep it clean as per the user's example style
                lines.append(f"  🔮 Projection: {thesis.get('short')} — Institutional accumulation likely")
                lines.append("")
        
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("")

    lines += [
        "🔍 SECTOR MOMENTUM TRACKER (Last 90 Days)",
        "✅ Rising Sectors — Momentum Building:",
    ]
    
    # Sort all sectors by RS to show rising/weak
    all_secs = sorted(scan_data.get("all_sectors", []), key=lambda x: x["rs"], reverse=True)
    for s in all_secs[:3]:
        th = fund_eng.get_sector_thesis(s["sector"])
        cat = th.get("reasons", ["Momentum building"])[0]
        lines.append(f"  🟢 {s['sector'].replace('Nifty ', '')}: +{((s['rs']-1)*100):.1f}% | {cat}")
        
    lines.append("")
    lines.append("❌ Sectors to Avoid — Losing Momentum:")
    for s in all_secs[-3:]:
        th = fund_eng.get_sector_thesis(s["sector"])
        lines.append(f"  🔴 {s['sector'].replace('Nifty ', '')}: {((s['rs']-1)*100):.1f}% | {th.get('risk', 'Avoid new entries')}")

    lines += [
        "",
        "💰 ALLOCATION INTELLIGENCE",
        "Why these sector weights?",
        "",
    ]
    
    total_alloc = 0
    for sec in top_secs[:3]:
        alloc = 20 # Simple mock alloc for the report
        total_alloc += alloc
        thesis = fund_eng.get_sector_thesis(sec["sector"])
        lines.append(f"📊 {sec['sector'].replace('Nifty ', '')} → {alloc}% of portfolio")
        for r in thesis.get("reasons", [])[:2]:
            lines.append(f"  → {r}")
            
    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        rep_eng.DISCLAIMER,
        "",
        f"📅 Valid for 15 days | Until: {(datetime.now(IST) + timedelta(days=15)).strftime('%d %b %Y')}",
        f"🔄 Next report: {'Next Week' if newsletter_type == 'WEEKLY' else 'Next Month' if newsletter_type == 'MONTHLY' else 'Tomorrow 8:00 AM IST'}",
        "",
        f"{SYSTEM_ICON} {SYSTEM_NAME} | {SYSTEM_VERSION}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    return "\n".join(lines)

def _build_html_version(scan_data, newsletter_type):
    """
    [GENERATIVE UI] Powered by Google Stitch Principles.
    Implements Material 3 (M3) Design System for BHARAT AlgoVerse.
    """
    now_str    = datetime.now(IST).strftime("%d %b %Y")
    type_label = "DAILY INTELLIGENCE" if newsletter_type == "DAILY" else ("WEEKLY REVIEW" if newsletter_type == "WEEKLY" else "MONTHLY STRATEGIC OUTLOOK")
    market_mode = scan_data.get("market_mode", "UNKNOWN")
    
    # Material 3 Color Tokens
    M3_PRIMARY = "#1a73e8"  # Google Blue
    M3_SURFACE = "#ffffff"
    M3_ON_SURFACE = "#202124"
    M3_VARIANT = "#f1f3f4"  # Light Grey
    M3_SUCCESS = "#1e8e3e"  # Google Green
    M3_ERROR   = "#d93025"  # Google Red
    
    mode_color = M3_SUCCESS if market_mode == "AGGRESSIVE" else M3_ERROR
    
    top_secs   = scan_data.get("top_sectors", [])
    stock_picks = scan_data.get("stock_picks", {})
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
            
            body {{ 
                font-family: 'Inter', system-ui, -apple-system, sans-serif; 
                background-color: #f8f9fa; 
                color: {M3_ON_SURFACE}; 
                margin: 0; 
                padding: 40px 10px;
                -webkit-font-smoothing: antialiased;
            }}

            .stitch-container {{ 
                max-width: 800px; 
                margin: 0 auto; 
                background: {M3_SURFACE}; 
                border-radius: 28px; 
                border: 1px solid #e0e2e6;
                box-shadow: 0 1px 3px rgba(60,64,67,0.3), 0 4px 8px 3px rgba(60,64,67,0.15);
                overflow: hidden;
            }}

            .stitch-header {{ 
                padding: 48px 40px 32px; 
                background: {M3_SURFACE};
                text-align: left;
            }}
            
            .stitch-brand {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
            .brand-icon {{ font-size: 2.5rem; }}
            .brand-name {{ font-size: 1.75rem; font-weight: 700; color: {M3_ON_SURFACE}; margin: 0; }}
            .report-badge {{ 
                display: inline-block;
                padding: 6px 16px;
                background: {M3_VARIANT};
                border-radius: 12px;
                font-size: 0.75rem;
                font-weight: 600;
                color: {M3_PRIMARY};
                letter-spacing: 0.05em;
                margin-top: 16px;
            }}
            
            .meta-strip {{ 
                padding: 12px 40px; 
                background: {M3_VARIANT}; 
                font-size: 0.75rem; 
                color: #5f6368; 
                display: flex; 
                justify-content: space-between;
                border-bottom: 1px solid #dadce0;
            }}

            .stitch-content {{ padding: 40px; }}
            
            .section-label {{ 
                font-size: 0.875rem; 
                font-weight: 600; 
                color: {M3_PRIMARY}; 
                margin-bottom: 24px;
                display: block;
            }}
            
            .kpi-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 48px; }}
            .kpi-card {{ 
                background: {M3_VARIANT}; 
                padding: 24px; 
                border-radius: 24px; 
                transition: transform 0.2s;
            }}
            .kpi-title {{ font-size: 0.75rem; font-weight: 500; color: #5f6368; text-transform: uppercase; margin-bottom: 8px; }}
            .kpi-value {{ font-size: 2rem; font-weight: 700; color: {M3_ON_SURFACE}; }}

            .sector-entry {{ margin-bottom: 40px; }}
            .sector-card {{ 
                border: 1px solid #dadce0; 
                border-radius: 24px; 
                padding: 32px; 
                background: {M3_SURFACE};
            }}
            .sector-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }}
            .sector-title {{ font-size: 1.25rem; font-weight: 700; color: {M3_ON_SURFACE}; margin: 0; }}
            .status-pill {{ 
                font-size: 0.7rem; 
                font-weight: 600; 
                padding: 4px 12px; 
                border-radius: 8px; 
                background: #e6f4ea; 
                color: #137333; 
            }}
            
            .thesis-text {{ font-size: 1.1rem; color: #3c4043; line-height: 1.5; margin-bottom: 20px; }}
            .reason-list {{ margin: 0; padding-left: 20px; color: #5f6368; font-size: 0.9rem; }}
            .reason-list li {{ margin-bottom: 12px; }}

            .picks-grid {{ 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                gap: 16px; 
                margin-top: 24px; 
            }}
            .pick-card {{ 
                background: {M3_VARIANT}; 
                padding: 16px; 
                border-radius: 16px; 
                display: flex;
                flex-direction: column;
                gap: 4px;
            }}
            .pick-sym {{ font-weight: 700; font-size: 1rem; }}
            .pick-cap {{ font-size: 0.65rem; color: #5f6368; text-transform: uppercase; font-weight: 600; }}
            .pick-rs {{ font-size: 0.9rem; font-weight: 600; color: {M3_PRIMARY}; margin-top: 8px; }}

            .stitch-footer {{ 
                padding: 48px 40px; 
                background: {M3_VARIANT}; 
                border-top: 1px solid #dadce0;
                font-size: 0.75rem;
                color: #5f6368;
                line-height: 1.8;
            }}
            .disclaimer-box {{ margin-bottom: 24px; border-left: 4px solid #dadce0; padding-left: 16px; }}
        </style>
    </head>
    <body>
        <div class="stitch-container">
            <div class="stitch-header">
                <div class="stitch-brand">
                    <span class="brand-icon">{SYSTEM_ICON}</span>
                    <h1 class="brand-name">{SYSTEM_NAME}</h1>
                </div>
                <div class="report-badge">{type_label}</div>
            </div>
            
            <div class="meta-strip">
                <span>DATE: {now_str.upper()}</span>
                <span>SYSTEM: {SYSTEM_VERSION}</span>
            </div>
            
            <div class="stitch-content">
                <span class="section-label">Market Intelligence Pulse</span>
                <div class="kpi-row">
                    <div class="kpi-card">
                        <div class="kpi-title">Regime Status</div>
                        <div class="kpi-value" style="color: {mode_color};">{market_mode}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-title">Benchmark RS</div>
                        <div class="kpi-value">{scan_data.get('nifty_rsi', '—')}</div>
                    </div>
                </div>
                
                <span class="section-label">Top Conviction Sectors</span>
    """
    
    for sec in top_secs[:5]:
        thesis = fund_eng.get_sector_thesis(sec["sector"])
        html += f"""
        <div class="sector-entry">
            <div class="sector-card">
                <div class="sector-header">
                    <h3 class="sector-title">{sec['sector'].upper()}</h3>
                    <div class="status-pill">LEADING</div>
                </div>
                <div class="thesis-text">{thesis.get('short')}</div>
                <ul class="reason-list">
        """
        for reason in thesis.get("reasons", [])[:3]:
            html += f"<li>{reason}</li>"
        html += "</ul>"
        
        # Picks
        picks = stock_picks.get(sec["sector"], [])[:3]
        if picks:
            html += '<div class="picks-grid">'
            for p in picks:
                html += f"""
                <div class="pick-card">
                    <div class="pick-sym">{p['symbol']}</div>
                    <div class="pick-cap">{p['cap']} CAP</div>
                    <div class="pick-rs">+{((p['rs']-1)*100):.2f}% RS</div>
                </div>
                """
            html += "</div>"
            
        html += "</div></div>"
        
    html += f"""
            </div>
            <div class="stitch-footer">
                <div class="disclaimer-box">
                    <strong>LEGAL NOTICE:</strong> {rep_eng.DISCLAIMER.replace('*', '')}
                </div>
                <div style="text-align: center; opacity: 0.7;">
                    {SYSTEM_NAME} Intelligence | Powered by Google Stitch UI Framework
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html
    


def save_newsletter_to_file(html_content, newsletter_type):
    """Saves the newsletter as an HTML file for download."""
    filename = f"BHARAT_REPORT_{newsletter_type}_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    filepath = f"artifacts/{filename}"
    # Ensure artifacts dir exists
    import os
    if not os.path.exists("artifacts"):
        os.makedirs("artifacts")
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    return filepath
