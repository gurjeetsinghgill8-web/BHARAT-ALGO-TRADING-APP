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
    
    # 2. Build Text (Telegram) version
    if newsletter_type == "WEEKLY":
        text_content = rep_eng.build_weekly_report(scan_data)
    elif newsletter_type == "MONTHLY":
        text_content = _build_monthly_report_text(scan_data)
    else:
        # Default DAILY uses the high-detail format
        text_content = rep_eng.build_daily_report(scan_data)
        
    # 3. Build HTML (Web/Dashboard) version
    html_content = _build_html_version(scan_data, newsletter_type)
    
    return {
        "text": text_content,
        "html": html_content,
        "data": scan_data,
        "type": newsletter_type,
        "date": datetime.now(IST).strftime("%d %b %Y %H:%M")
    }

def _build_monthly_report_text(scan_data):
    """Monthly summary — high-level strategic view."""
    now_str = datetime.now(IST).strftime("%B %Y")
    top_secs = scan_data.get("top_sectors", [])
    pulse = scan_data.get("pulse", {})
    
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{SYSTEM_ICON} {SYSTEM_NAME} | MONTHLY STRATEGY",
        f"📅 Review: {now_str}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "📊 MONTHLY MARKET CLARITY",
        f"Nifty 50 Trend: {'🟢 POSITIVE' if scan_data.get('market_mode') == 'AGGRESSIVE' else '🔴 DEFENSIVE'}",
        "",
        "🏆 LONG-TERM SECTOR DOMINANCE",
        "Top sectors to hold for the next 30 days:",
    ]
    
    for i, sec in enumerate(top_secs[:3], 1):
        thesis = fund_eng.get_sector_thesis(sec["sector"])
        lines.append(f"{i}. {sec['sector'].replace('Nifty ', '').upper()}")
        lines.append(f"   💡 {thesis.get('short')}")
        
    lines += [
        "",
        "📉 SECTOR WEIGHTS (Strategic Allocation)",
    ]
    
    for sec in top_secs[:5]:
        lines.append(f"  • {sec['sector'].replace('Nifty ', '')}: Overweight")
        
    lines += [
        "",
        rep_eng.DISCLAIMER,
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    return "\n".join(lines)

def _build_html_version(scan_data, newsletter_type):
    """
    Builds a beautiful HTML version of the newsletter for the dashboard.
    Uses CSS for premium look.
    """
    now_str = datetime.now(IST).strftime("%d %b %Y")
    type_label = newsletter_type.capitalize()
    market_mode = scan_data.get("market_mode", "UNKNOWN")
    mode_color = "#10b981" if market_mode == "AGGRESSIVE" else "#f43f5e"
    
    top_secs = scan_data.get("top_sectors", [])
    stock_picks = scan_data.get("stock_picks", {})
    
    html = f"""
    <div style="font-family: 'Outfit', sans-serif; color: #e2e8f0; background: #0a0e1a; padding: 20px; border-radius: 16px; border: 1px solid #1e3a5f;">
        <div style="text-align: center; border-bottom: 2px solid #1e3a5f; padding-bottom: 20px; margin-bottom: 20px;">
            <div style="font-size: 2.5rem; font-weight: 700; color: #6366f1;">{SYSTEM_ICON} {SYSTEM_NAME}</div>
            <div style="font-size: 1rem; color: #94a3b8; letter-spacing: 2px;">{type_label.upper()} INTELLIGENCE REPORT | {now_str}</div>
        </div>
        
        <div style="display: flex; gap: 20px; margin-bottom: 30px;">
            <div style="flex: 1; background: rgba(255,255,255,0.03); padding: 20px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); text-align: center;">
                <div style="color: #64748b; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 8px;">Market Pulse</div>
                <div style="font-size: 1.8rem; font-weight: 700; color: {mode_color};">{market_mode}</div>
            </div>
            <div style="flex: 1; background: rgba(255,255,255,0.03); padding: 20px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05); text-align: center;">
                <div style="color: #64748b; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 8px;">Nifty RSI</div>
                <div style="font-size: 1.8rem; font-weight: 700; color: #6366f1;">{scan_data.get('nifty_rsi', '—')}</div>
            </div>
        </div>
        
        <h3 style="color: #94a3b8; font-size: 0.9rem; text-transform: uppercase; border-left: 4px solid #6366f1; padding-left: 10px; margin-bottom: 20px;">🏆 Sector Leadership Board</h3>
    """
    
    for sec in top_secs[:3]:
        thesis = fund_eng.get_sector_thesis(sec["sector"])
        html += f"""
        <div style="background: rgba(99,102,241,0.05); border: 1px solid rgba(99,102,241,0.1); border-radius: 12px; padding: 20px; margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <div style="font-size: 1.3rem; font-weight: 600; color: #e2e8f0;">{sec['sector'].upper()}</div>
                <div style="background: rgba(16,185,129,0.1); color: #10b981; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600;">STRONG LEADER</div>
            </div>
            <div style="color: #94a3b8; font-style: italic; margin-bottom: 15px;">"{thesis.get('short')}"</div>
            <ul style="color: #cbd5e1; font-size: 0.9rem; padding-left: 20px;">
        """
        for reason in thesis.get("reasons", [])[:2]:
            html += f"<li style='margin-bottom: 5px;'>{reason}</li>"
            
        html += "</ul></div>"
        
    html += """
        <div style="margin-top: 30px; padding: 20px; border-top: 1px solid #1e3a5f; font-size: 0.75rem; color: #475569; line-height: 1.5;">
            <strong>⚠️ DISCLAIMER:</strong> This is independent market research for educational purposes only. It is NOT investment advice. Past momentum does not guarantee future returns. Consult a SEBI-registered advisor before making any investment decision.
        </div>
        <div style="text-align: center; margin-top: 10px; color: #64748b; font-size: 0.8rem;">
            Generated by BHARAT AlgoVerse v3.1 | BMC v3.1
        </div>
    </div>
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
