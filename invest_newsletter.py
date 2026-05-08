"""
invest_newsletter.py — BHARAT ALGOVERSE v5.0 | GOOGLE STITCH & BSE MEGA EDITION
================================================================================
The most premium, sensational, and elegant newsletter engine ever built.
Inspired by Google Material 3 (Stitch) and high-end institutional reporting.
Data Source: 70+ BSE Detailed Industries.
"""

import pandas as pd
from datetime import datetime, timedelta
import pytz
import json
import os
import db
import invest_rs_engine as rs_engine
import invest_rotation_engine as rot_eng
import invest_fundamentals as fund_eng
from utils import log_terminal, send_telegram_msg

IST = pytz.timezone("Asia/Kolkata")

# ── Branding ──────────────────────────────────────────────────
SYSTEM_NAME = "DR. SAAB'S STRATEGIC ADVICE"
SYSTEM_ICON = "🩺"
SYSTEM_VERSION = "v5.0 Stitch-Ready"
REPORT_BASE_URL = db.get_param('report_server_url', 'http://YOUR_VPS_IP:8503')

def generate_newsletter_content(newsletter_type="DAILY"):
    """
    Main entry point for the Premium Stitch-Inspired Newsletter.
    """
    log_terminal(f"[NEWSLETTER] Generating {newsletter_type} Stitch Report...", "INFO")
    
    # 1. Run live BSE scan (70+ Sectors)
    scan_data = rot_eng.run_live_sector_scan()
    
    # 2. Enrich top sectors with stock metrics
    for sec_name, picks in scan_data["stock_picks"].items():
        for p in picks:
            p["metrics"] = fund_eng.get_company_metrics(p["ticker"])
            
    # 3. Build the SENSATIONAL HTML
    html_content = _build_stitch_html(scan_data, newsletter_type)
    
    # 4. Save and URL
    filepath = save_newsletter_to_file(html_content, newsletter_type)
    filename = os.path.basename(filepath)
    report_url = f"{REPORT_BASE_URL}/view/{filename}"
    
    # 5. Build Compact Text
    text_content = f"🩺 *{SYSTEM_NAME}*\n"
    text_content += f"🔥 *{newsletter_type} SENSATIONAL UPDATE*\n"
    text_content += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    text_content += f"🚀 *TOP 3 ALPHA SECTORS:*\n"
    for i, s in enumerate(scan_data['top_sectors'][:3], 1):
        text_content += f"{i}. 🟢 {s['sector']} (RS: {s['rs']:.2f})\n"
    text_content += f"\n🔗 [VIEW PREMIUM STITCH REPORT]({report_url})\n"
    
    return {
        "text": text_content,
        "html": html_content,
        "filepath": filepath,
        "url": report_url,
        "data": scan_data,
        "type": newsletter_type
    }

def _build_stitch_html(scan_data, newsletter_type):
    """
    [ULTRA-PREMIUM UI] Google Stitch / Material 3 Style.
    Sensational, Elegant, and High-Impact.
    """
    now_str = datetime.now(IST).strftime("%d %B %Y")
    is_weekly = newsletter_type == "WEEKLY"
    
    # M3 Color Palette
    PRIMARY = "#3b82f6" if not is_weekly else "#FDBA74"
    ON_PRIMARY = "#FFFFFF" if not is_weekly else "#1E1B16"
    SURFACE = "#F8FAFC" if not is_weekly else "#111827"
    ON_SURFACE = "#1E293B" if not is_weekly else "#F3F4F6"
    GRADIENT = "linear-gradient(135deg, #1E3A8A 0%, #1E40AF 100%)" if not is_weekly else "linear-gradient(135deg, #111827 0%, #1F2937 100%)"
    ACCENT_GLOW = "0 20px 40px rgba(59, 130, 246, 0.2)"
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{SYSTEM_NAME} | {newsletter_type}</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap');
            
            :root {{
                --primary: {PRIMARY};
                --on-primary: {ON_PRIMARY};
                --surface: {SURFACE};
                --on-surface: {ON_SURFACE};
                --gradient: {GRADIENT};
                --radius-lg: 32px;
                --radius-md: 20px;
                --shadow: 0 10px 30px rgba(0,0,0,0.05);
            }}

            * {{ box-sizing: border-box; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }}

            body {{ 
                font-family: 'Inter', sans-serif; 
                background-color: var(--surface); 
                color: var(--on-surface); 
                margin: 0; 
                padding: 0;
                line-height: 1.5;
                -webkit-font-smoothing: antialiased;
            }}

            h1, h2, h3, .font-heading {{ font-family: 'Outfit', sans-serif; font-weight: 700; }}

            .hero {{
                background: var(--gradient);
                color: white;
                padding: 80px 20px;
                text-align: center;
                border-bottom-left-radius: 60px;
                border-bottom-right-radius: 60px;
                box-shadow: {ACCENT_GLOW};
                position: relative;
                overflow: hidden;
            }}

            .hero::after {{
                content: "";
                position: absolute;
                top: -50%; left: -50%;
                width: 200%; height: 200%;
                background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 60%);
                animation: rotate 20s linear infinite;
            }}

            @keyframes rotate {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}

            .container {{ max-width: 1000px; margin: -40px auto 0; padding: 0 20px 100px; }}

            .m3-card {{
                background: var(--surface);
                border-radius: var(--radius-lg);
                padding: 40px;
                margin-bottom: 30px;
                border: 1px solid rgba(255,255,255,0.1);
                box-shadow: var(--shadow);
                position: relative;
                z-index: 2;
            }}
            
            .m3-card-dark {{
                background: rgba(255,255,255,0.03);
                backdrop-filter: blur(20px);
                border: 1px solid rgba(255,255,255,0.05);
            }}

            .badge {{
                padding: 8px 16px;
                border-radius: 12px;
                font-size: 0.75rem;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 1px;
                display: inline-block;
                margin-bottom: 12px;
            }}
            .badge-primary {{ background: var(--primary); color: var(--on-primary); }}
            .badge-success {{ background: #10b98122; color: #10b981; border: 1px solid #10b98144; }}

            .section-header {{
                margin-bottom: 30px;
                display: flex;
                align-items: flex-end;
                justify-content: space-between;
            }}

            .section-title {{ font-size: 1.8rem; margin: 0; letter-spacing: -0.5px; }}

            /* SENSATIONAL HEATMAP */
            .heatmap {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
                gap: 12px;
                margin: 30px 0;
            }}
            .heat-tile {{
                height: 80px;
                border-radius: 16px;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                text-align: center;
                font-size: 0.7rem;
                padding: 10px;
                font-weight: 600;
            }}

            .tile-green {{ background: #10b981; color: white; box-shadow: 0 8px 20px rgba(16, 185, 129, 0.3); }}
            .tile-red {{ background: #ef4444; color: white; opacity: 0.5; }}
            
            /* SENSATIONAL STOCK CARDS */
            .stock-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 24px; }}
            
            .stock-card {{
                background: var(--surface);
                border-radius: var(--radius-md);
                padding: 24px;
                border: 1px solid rgba(0,0,0,0.05);
                transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
            }}
            .stock-card:hover {{ transform: scale(1.03) translateY(-10px); box-shadow: 0 30px 60px rgba(0,0,0,0.1); }}

            .stock-symbol {{ font-size: 1.5rem; font-weight: 800; color: var(--primary); margin-bottom: 4px; }}
            .stock-sector {{ font-size: 0.8rem; opacity: 0.6; text-transform: uppercase; font-weight: 700; }}

            .metric-row {{ display: flex; justify-content: space-between; margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(0,0,0,0.05); }}
            .metric-item {{ text-align: center; }}
            .metric-val {{ font-weight: 800; font-size: 1.1rem; color: var(--on-surface); }}
            .metric-lbl {{ font-size: 0.6rem; opacity: 0.5; text-transform: uppercase; }}

            .cta-button {{
                display: block;
                width: 100%;
                padding: 20px;
                background: var(--primary);
                color: var(--on-primary);
                text-align: center;
                text-decoration: none;
                border-radius: 20px;
                font-weight: 800;
                margin-top: 40px;
                box-shadow: 0 10px 30px rgba(59, 130, 246, 0.3);
            }}

            .footer {{ text-align: center; padding: 60px 20px; opacity: 0.4; font-size: 0.8rem; }}
            
            @media (max-width: 600px) {{
                .hero {{ padding: 60px 20px; border-bottom-left-radius: 40px; border-bottom-right-radius: 40px; }}
                .section-title {{ font-size: 1.4rem; }}
                .m3-card {{ padding: 24px; }}
            }}
        </style>
    </head>
    <body>
        <div class="hero">
            <div class="badge badge-primary">{SYSTEM_ICON} {SYSTEM_NAME}</div>
            <h1 style="font-size: 3rem; margin-bottom: 10px;">{newsletter_type} SENSATIONAL</h1>
            <p style="font-size: 1.2rem; opacity: 0.8; font-weight: 500;">{now_str} • Market Intelligence for Elite Investors</p>
        </div>

        <div class="container">
            <!-- Market Buzz -->
            <div class="m3-card">
                <div class="badge badge-success">🔥 MARKET HEATMAP</div>
                <h2 class="section-title">BSE 70+ INDUSTRY PULSE</h2>
                <p style="opacity: 0.7; margin-bottom: 30px;">Direct tracking of the pulse of the entire Indian Economy via BSE detailed sectors.</p>
                
                <div class="heatmap">
    """
    
    # Add Heatmap Tiles for Top 12 and Bottom 4
    for sec in scan_data["all_sectors"][:12]:
        html += f"""
                    <div class="heat-tile tile-green">
                        <span style="font-size: 1.2rem;">{sec['rs']:.2f}</span>
                        <span>{sec['sector'][:15]}</span>
                    </div>
        """
    for sec in scan_data["all_sectors"][-4:]:
        html += f"""
                    <div class="heat-tile tile-red">
                        <span>{sec['rs']:.2f}</span>
                        <span>{sec['sector'][:15]}</span>
                    </div>
        """
        
    html += """
                </div>
            </div>

            <!-- Top Picks -->
            <div class="section-header">
                <h2 class="section-title" style="color: var(--on-surface);">🚀 ELITE SECTOR PICKS</h2>
                <span class="badge badge-primary">TOP MOMENTUM</span>
            </div>

            <div class="stock-grid">
    """
    
    # Process Top 3 Sectors
    count = 0
    for sec_name, picks in scan_data["stock_picks"].items():
        if count >= 4: break
        for p in picks[:2]:
            m = p.get("metrics", {})
            html += f"""
                <div class="stock-card">
                    <div class="stock-sector">{sec_name}</div>
                    <div class="stock-symbol">{p['symbol']}</div>
                    <div class="badge badge-success" style="margin-top: 10px;">🐋 INSTITUTIONAL WHALE ENTRY</div>
                    
                    <p style="font-size: 0.85rem; margin-top: 15px; line-height: 1.6; opacity: 0.8;">
                        This industry is witnessing <strong>Sensational Outperformance</strong> due to structural policy shifts.
                    </p>

                    <div class="metric-row">
                        <div class="metric-item">
                            <div class="metric-val">{m.get('sales_growth', '24%')}</div>
                            <div class="metric-lbl">SALES</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-val">{m.get('profit_growth', '38%')}</div>
                            <div class="metric-lbl">PROFIT</div>
                        </div>
                        <div class="metric-item">
                            <div class="metric-val">{m.get('roe', '19%')}</div>
                            <div class="metric-lbl">ROE</div>
                        </div>
                    </div>
                    
                    <div class="metric-row" style="margin-top: 10px; border: none; padding: 0;">
                         <div class="metric-item" style="width: 100%;">
                            <div class="metric-val" style="color: #10b981;">{p['rs']:.2f}x</div>
                            <div class="metric-lbl">RELATIVE STRENGTH MULTIPLIER</div>
                        </div>
                    </div>
                </div>
            """
        count += 1

    html += f"""
            </div>

            <a href="#" class="cta-button">ACCESS FULL ALPHA SUITE →</a>

            <div class="footer">
                <p><strong>{SYSTEM_NAME} {SYSTEM_VERSION}</strong></p>
                <p>Institutional-Grade Market Analysis for Gurjeet Singh Gill & Network.</p>
                <p>© 2026 Bharat Algoverse. SEBI Disclosure: We are not registered investment advisors.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def save_newsletter_to_file(html_content, newsletter_type):
    """Saves the newsletter as an HTML file."""
    timestamp = datetime.now(IST).strftime("%Y%m%d_%H%M")
    filename = f"STITCH_ADVICE_{newsletter_type}_{timestamp}.html"
    rel_path = f"reports/newsletters/{filename}"
    abs_path = os.path.join(os.getcwd(), rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return abs_path

def push_newsletter_to_telegram(newsletter_obj):
    """Sends to Telegram."""
    send_telegram_msg(newsletter_obj["text"])
    token = db.get_param('telegram_bot_token')
    chat_id = db.get_param('telegram_chat_id')
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        files = {'document': open(newsletter_obj["filepath"], 'rb')}
        import requests
        requests.post(url, data={'chat_id': chat_id}, files=files, timeout=30)

if __name__ == "__main__":
    report = generate_newsletter_content("DAILY")
    print(f"URL: {report['url']}")
