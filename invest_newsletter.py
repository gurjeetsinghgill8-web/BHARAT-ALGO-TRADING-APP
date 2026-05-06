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
    Builds a premium, LIGHT THEME financial intelligence report.
    Inspired by Bloomberg/Financial Times layout.
    """
    now_str    = datetime.now(IST).strftime("%d %b %Y")
    type_label = "DAILY INTELLIGENCE" if newsletter_type == "DAILY" else ("WEEKLY REVIEW" if newsletter_type == "WEEKLY" else "MONTHLY STRATEGIC OUTLOOK")
    market_mode = scan_data.get("market_mode", "UNKNOWN")
    mode_color = "#059669" if market_mode == "AGGRESSIVE" else "#dc2626"
    
    top_secs   = scan_data.get("top_sectors", [])
    stock_picks = scan_data.get("stock_picks", {})
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
            
            :root {{
                --primary: #1e3a8a;
                --secondary: #6366f1;
                --accent: #0f172a;
                --bg: #f8fafc;
                --card: #ffffff;
                --text-main: #1e293b;
                --text-muted: #64748b;
                --border: #e2e8f0;
            }}

            body {{ 
                font-family: 'Inter', -apple-system, sans-serif; 
                background-color: var(--bg); 
                color: var(--text-main); 
                margin: 0; 
                padding: 40px 20px; 
                line-height: 1.6;
            }}

            .container {{ 
                max-width: 850px; 
                margin: 0 auto; 
                background: var(--card); 
                border-radius: 4px; 
                border-top: 8px solid var(--primary);
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            }}

            .header {{ 
                padding: 60px 50px 40px; 
                text-align: left; 
                border-bottom: 1px solid var(--border);
                display: flex;
                justify-content: space-between;
                align-items: flex-end;
            }}
            
            .branding {{ flex: 1; }}
            .brand-name {{ font-size: 2.4rem; font-weight: 800; color: var(--accent); margin: 0; letter-spacing: -0.04em; }}
            .brand-tagline {{ font-size: 0.85rem; color: var(--secondary); font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; margin-top: 5px; }}
            
            .report-meta {{ text-align: right; }}
            .report-type {{ font-size: 0.9rem; font-weight: 700; color: var(--text-main); margin-bottom: 5px; }}
            .report-date {{ font-size: 0.8rem; color: var(--text-muted); }}

            .content {{ padding: 50px; }}
            
            .section-header {{ 
                display: flex; 
                align-items: center; 
                margin: 40px 0 25px; 
                padding-bottom: 10px;
                border-bottom: 2px solid var(--accent);
            }}
            .section-title {{ font-size: 1.2rem; font-weight: 800; color: var(--accent); text-transform: uppercase; margin: 0; }}
            
            .pulse-grid {{ display: grid; grid-template-columns: 1fr 1.5fr; gap: 30px; margin-bottom: 40px; }}
            .pulse-card {{ background: #f1f5f9; padding: 25px; border-radius: 8px; border-left: 4px solid var(--primary); }}
            .pulse-label {{ font-size: 0.75rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 10px; }}
            .pulse-val {{ font-size: 1.6rem; font-weight: 800; color: var(--accent); }}
            .pulse-desc {{ font-size: 0.9rem; color: var(--text-muted); margin-top: 10px; }}

            .sector-entry {{ margin-bottom: 50px; }}
            .sector-meta {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 15px; }}
            .sector-name {{ font-size: 1.5rem; font-weight: 700; color: var(--primary); }}
            .sector-status {{ font-size: 0.75rem; font-weight: 700; color: #059669; background: #ecfdf5; padding: 4px 12px; border-radius: 4px; }}
            
            .thesis-box {{ background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 25px; margin-bottom: 20px; }}
            .thesis-text {{ font-size: 1.1rem; font-weight: 500; color: var(--text-main); margin-bottom: 15px; line-height: 1.4; }}
            .thesis-list {{ margin: 0; padding-left: 20px; color: var(--text-muted); font-size: 0.95rem; }}
            .thesis-list li {{ margin-bottom: 8px; }}

            .picks-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            .picks-table th {{ text-align: left; font-size: 0.7rem; text-transform: uppercase; color: var(--text-muted); padding: 10px; border-bottom: 1px solid var(--border); }}
            .picks-table td {{ padding: 15px 10px; border-bottom: 1px solid #f1f5f9; font-size: 0.9rem; }}
            .symbol-col {{ font-weight: 700; color: var(--accent); }}
            .cap-badge {{ font-size: 0.65rem; padding: 2px 6px; background: #e2e8f0; border-radius: 3px; font-weight: 600; }}

            .footer {{ padding: 60px 50px; background: #f8fafc; border-top: 1px solid var(--border); }}
            .disclaimer {{ font-size: 0.75rem; color: #94a3b8; line-height: 1.6; text-align: justify; }}
            .signature {{ margin-top: 30px; text-align: center; font-size: 0.8rem; color: var(--text-muted); font-weight: 500; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="branding">
                    <h1 class="brand-name">{SYSTEM_NAME}</h1>
                    <div class="brand-tagline">{SYSTEM_TAGLINE}</div>
                </div>
                <div class="report-meta">
                    <div class="report-type">{type_label}</div>
                    <div class="report-date">{now_str.upper()}</div>
                </div>
            </div>
            
            <div class="content">
                <div class="section-header">
                    <h2 class="section-title">Market Regime Assessment</h2>
                </div>
                
                <div class="pulse-grid">
                    <div class="pulse-card">
                        <div class="pulse-label">Current Mode</div>
                        <div class="pulse-val" style="color: {mode_color};">{market_mode}</div>
                        <div class="pulse-desc">{'Strategic positioning: Risk-on / Aggressive accumulation.' if market_mode == 'AGGRESSIVE' else 'Strategic positioning: Capital preservation / Defensive.'}</div>
                    </div>
                    <div class="pulse-card" style="border-left-color: var(--secondary);">
                        <div class="pulse-label">Relative Strength Index</div>
                        <div class="pulse-val">{scan_data.get('nifty_rsi', '—')}</div>
                        <div class="pulse-desc">Nifty 50 benchmark momentum factor vs 14-period standard.</div>
                    </div>
                </div>
                
                <div class="section-header">
                    <h2 class="section-title">High-Conviction Sector Leadership</h2>
                </div>
    """
    
    for sec in top_secs[:5]:
        thesis = fund_eng.get_sector_thesis(sec["sector"])
        html += f"""
        <div class="sector-entry">
            <div class="sector-meta">
                <div class="sector-name">{sec['sector'].upper()}</div>
                <div class="sector-status">MOMENTUM LEADER</div>
            </div>
            
            <div class="thesis-box">
                <div class="thesis-text">"{thesis.get('short')}"</div>
                <ul class="thesis-list">
        """
        for reason in thesis.get("reasons", [])[:3]:
            html += f"<li>{reason}</li>"
        html += "</ul></div>"
        
        # Stocks Table
        picks = stock_picks.get(sec["sector"], [])[:3]
        if picks:
            html += """
            <table class="picks-table">
                <thead>
                    <tr>
                        <th style="width: 40%;">Ticker / Cap</th>
                        <th style="width: 30%;">Strength Label</th>
                        <th style="width: 30%; text-align: right;">Momentum RS</th>
                    </tr>
                </thead>
                <tbody>
            """
            for p in picks:
                st_label = "EXCEPTIONAL" if p.get("rs", 0) > 1.1 else "OUTPERFORMING"
                html += f"""
                <tr>
                    <td>
                        <span class="symbol-col">{p['symbol']}</span> 
                        <span class="cap-badge">{p['cap'].upper()}</span>
                    </td>
                    <td style="font-weight: 600; font-size: 0.8rem; color: var(--secondary);">{st_label}</td>
                    <td style="text-align: right; font-weight: 700; color: var(--primary);">+{((p['rs']-1)*100):.2f}%</td>
                </tr>
                """
            html += "</tbody></table>"
        html += "</div>"
        
    html += f"""
            </div>
            <div class="footer">
                <div class="disclaimer">
                    <strong>⚠️ CONFIDENTIAL & PROPRIETARY:</strong> {rep_eng.DISCLAIMER.replace('*', '')}
                </div>
                <div class="signature">
                    {SYSTEM_NAME} | {SYSTEM_VERSION} | India Market Intelligence Unit
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
