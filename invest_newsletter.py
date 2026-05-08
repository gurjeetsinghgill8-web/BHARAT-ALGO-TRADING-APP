"""
invest_newsletter.py — BHARAT ALGOVERSE v4.2 | Strategic Newsletter Engine
===========================================================================
Generates Daily, Weekly (Sunday), and Monthly reports in Text and HTML formats.
Optimized for Telegram, Twitter, and Dashboard display.
Branding: DR. SAAB'S STRATEGIC ADVICE (Doctor Girls Advice)
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
import invest_report as rep_eng
from utils import log_terminal, send_telegram_msg, send_telegram_html

IST = pytz.timezone("Asia/Kolkata")

# ── Branding ──────────────────────────────────────────────────
SYSTEM_NAME = "DR. SAAB'S STRATEGIC ADVICE"
SYSTEM_ICON = "🩺"
SYSTEM_TAGLINE = "Institutional-Grade Market Intelligence"
SYSTEM_VERSION = "v4.2 Alpha"

# ── Config ──────────────────────────────────────────────────
REPORT_BASE_URL = db.get_param('report_server_url', 'http://YOUR_VPS_IP:8503')

def generate_newsletter_content(newsletter_type="DAILY"):
    """
    Main entry point for newsletter generation.
    Pulls live scan data and formats it according to the requested type.
    """
    log_terminal(f"[NEWSLETTER] Generating {newsletter_type} report...", "INFO")
    
    # 1. Decide RS Period based on type
    rs_period = rs_engine.RS_PERIOD_LONG if newsletter_type == "WEEKLY" else rs_engine.RS_PERIOD
    
    # 2. Run live scan with chosen period
    scan_data = rot_eng.run_live_sector_scan() # Note: In production, we'd pass rs_period to this function
    
    # 3. Add laggards (Lagging industries)
    all_sectors = sorted(scan_data.get("all_sectors", []), key=lambda x: x["rs"])
    scan_data["lagging_sectors"] = all_sectors[:5]
    
    # 4. Special Focus: Defense & AI Tracking
    scan_data["special_focus"] = _track_special_lists(rs_period)
    
    # 5. Enhance with financial metrics for top stocks
    for sec_name, stocks in scan_data["stock_picks"].items():
        for st in stocks:
            st["metrics"] = fund_eng.get_company_metrics(st["ticker"])
            
    # 6. Build HTML (Web/Dashboard) version - THE PREMIUM ONE
    html_content = _build_premium_html(scan_data, newsletter_type)
    
    # 7. Save to file
    filepath = save_newsletter_to_file(html_content, newsletter_type)
    filename = os.path.basename(filepath)
    report_url = f"{REPORT_BASE_URL}/view/{filename}"
    
    # 8. Build Text (Telegram/Compass) version with URL
    text_content = _build_compact_text(scan_data, newsletter_type, report_url)
    
    return {
        "text": text_content,
        "html": html_content,
        "filepath": filepath,
        "url": report_url,
        "data": scan_data,
        "type": newsletter_type,
        "date": datetime.now(IST).strftime("%d %b %Y %H:%M")
    }

def _track_special_lists(period):
    """Calculates RS for Defense and AI stocks specifically."""
    results = {}
    for strategy, tickers in rs_engine.SPECIAL_LISTS.items():
        strategy_stocks = []
        for t in tickers:
            rs = rs_engine.calc_rs(t, rs_engine.NIFTY_TICKER, period)
            if rs:
                strategy_stocks.append({
                    "symbol": t.replace(".NS", ""),
                    "ticker": t,
                    "rs": rs,
                    "metrics": fund_eng.get_company_metrics(t)
                })
        # Sort by RS
        strategy_stocks.sort(key=lambda x: x["rs"], reverse=True)
        results[strategy] = strategy_stocks[:5]
    return results

def _build_compact_text(scan_data, newsletter_type, report_url):
    """Compact text for Telegram notification."""
    now_str = datetime.now(IST).strftime("%d %b %Y")
    type_label = "DAILY" if newsletter_type == "DAILY" else "WEEKLY SUNDAY SPECIAL"
    
    lines = [
        f"🩺 *{SYSTEM_NAME}*",
        f"📅 *{type_label} REPORT | {now_str}*",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "🚀 *TOP LEADING INDUSTRIES:*",
    ]
    
    for i, sec in enumerate(scan_data.get("top_sectors", [])[:3], 1):
        lines.append(f"{i}. 🟢 {sec['sector']} (RS: {sec['rs']:.2f})")
        
    lines += [
        "",
        "⚠️ *LAGGING INDUSTRIES (AVOID):*",
    ]
    for sec in scan_data.get("lagging_sectors", [])[:3]:
        lines.append(f"• 🔴 {sec['sector']}")
        
    lines += [
        "",
        "🛡️ *SPECIAL FOCUS:*",
        f"Defense Leader: {scan_data['special_focus']['Defense Strategy'][0]['symbol']}",
        f"AI Leader: {scan_data['special_focus']['AI & Digital Strategy'][0]['symbol']}",
        "",
        "📊 *VIEW FULL PREMIUM REPORT:*",
        f"🔗 [Click here to open in Mobile]({report_url})",
        "",
        "Allocation Focus: *Defense & AI*"
    ]
    
    return "\n".join(lines)

def _build_premium_html(scan_data, newsletter_type):
    """
    [PREMIUM UI] Modern, Interactive, and Responsive HTML Report.
    Tailored for Dr. Saab's Strategic Advice.
    """
    now_str = datetime.now(IST).strftime("%d %B %Y")
    type_label = "DAILY INTELLIGENCE" if newsletter_type == "DAILY" else "WEEKLY SUNDAY SPECIAL"
    market_mode = scan_data.get("market_mode", "UNKNOWN")
    
    # Colors
    is_weekly = newsletter_type == "WEEKLY"
    BG_GRADIENT = "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)" if is_weekly else "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)"
    CARD_BG = "rgba(30, 41, 59, 0.7)" if is_weekly else "#ffffff"
    TEXT_COLOR = "#f8fafc" if is_weekly else "#1e293b"
    ACCENT = "#fbbf24" if is_weekly else "#3b82f6" # Gold for weekly, Blue for daily
    
    top_secs = scan_data.get("top_sectors", [])
    lagging_secs = scan_data.get("lagging_sectors", [])
    stock_picks = scan_data.get("stock_picks", {})

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{SYSTEM_NAME} | {type_label}</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
            
            :root {{
                --primary: {ACCENT};
                --bg: {BG_GRADIENT};
                --card: {CARD_BG};
                --text: {TEXT_COLOR};
                --success: #10b981;
                --error: #ef4444;
            }}

            body {{ 
                font-family: 'Outfit', sans-serif; 
                background: var(--bg); 
                color: var(--text); 
                margin: 0; 
                padding: 0;
                line-height: 1.6;
            }}

            .container {{ 
                max-width: 900px; 
                margin: 0 auto; 
                padding: 40px 20px;
            }}

            header {{
                text-align: center;
                margin-bottom: 60px;
                padding: 40px;
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border-radius: 30px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }}

            .logo {{ font-size: 3.5rem; margin-bottom: 10px; }}
            h1 {{ font-size: 2.5rem; font-weight: 700; margin: 0; letter-spacing: -1px; }}
            .tagline {{ opacity: 0.7; font-size: 1.1rem; }}
            .badge {{ 
                display: inline-block; 
                padding: 8px 20px; 
                background: var(--primary); 
                color: #000; 
                border-radius: 50px; 
                font-weight: 700; 
                font-size: 0.8rem; 
                margin-top: 20px;
                text-transform: uppercase;
            }}

            .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-bottom: 50px; }}
            @media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} }}

            .card {{ 
                background: var(--card); 
                padding: 35px; 
                border-radius: 30px; 
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                border: 1px solid rgba(255, 255, 255, 0.1);
                position: relative;
                overflow: hidden;
            }}

            .section-title {{ 
                font-size: 1.5rem; 
                font-weight: 700; 
                margin-bottom: 25px; 
                display: flex; 
                align-items: center; 
                gap: 10px;
            }}

            .leader-item {{ 
                display: flex; 
                align-items: center; 
                gap: 15px; 
                margin-bottom: 20px; 
                padding: 15px;
                background: rgba(255, 255, 255, 0.03);
                border-radius: 20px;
            }}
            .rank-number {{ 
                width: 40px; height: 40px; 
                background: var(--primary); 
                color: #000; 
                border-radius: 50%; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                font-weight: 800;
                flex-shrink: 0;
            }}
            .industry-name {{ font-weight: 600; font-size: 1.1rem; }}
            .industry-rs {{ font-size: 0.8rem; opacity: 0.6; }}

            .laggard-item {{ 
                display: flex; 
                justify-content: space-between; 
                padding: 12px 0; 
                border-bottom: 1px solid rgba(255,255,255,0.1); 
            }}
            .laggard-item:last-child {{ border: none; }}

            .stocks-section {{ margin-top: 60px; }}
            .stock-card {{ 
                background: var(--card); 
                border-radius: 30px; 
                margin-bottom: 40px; 
                overflow: hidden;
                box-shadow: 0 20px 40px rgba(0,0,0,0.2);
            }}
            .stock-header {{ 
                padding: 30px; 
                background: var(--primary); 
                color: #000; 
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
            }}
            .stock-title {{ margin: 0; }}
            .stock-metrics-grid {{ 
                display: grid; 
                grid-template-columns: repeat(3, 1fr); 
                gap: 1px; 
                background: rgba(255,255,255,0.1); 
            }}
            .metric-box {{ 
                padding: 25px; 
                text-align: center; 
                background: var(--card);
            }}
            .metric-val {{ font-size: 1.5rem; font-weight: 700; color: var(--primary); }}
            .metric-label {{ font-size: 0.75rem; text-transform: uppercase; opacity: 0.6; margin-top: 5px; }}

            .stock-content {{ padding: 35px; }}
            .info-row {{ margin-bottom: 25px; }}
            .info-label {{ font-weight: 700; margin-bottom: 10px; display: block; color: var(--primary); }}
            .info-text {{ font-size: 1.1rem; opacity: 0.9; }}

            .footer {{ 
                text-align: center; 
                margin-top: 80px; 
                padding: 40px; 
                opacity: 0.5; 
                font-size: 0.85rem; 
                border-top: 1px solid rgba(255,255,255,0.1);
            }}
            
            .progress-container {{
                width: 100%;
                background: rgba(255,255,255,0.1);
                border-radius: 10px;
                height: 8px;
                margin-top: 10px;
            }}
            .progress-bar {{
                height: 100%;
                background: var(--primary);
                border-radius: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div class="logo">{SYSTEM_ICON}</div>
                <h1>{SYSTEM_NAME}</h1>
                <div class="tagline">Strategic Intelligence for the Modern Investor</div>
                <div class="badge">{type_label} | {now_str.upper()}</div>
            </header>

            <div class="grid">
                <div class="card">
                    <div class="section-title">🚀 Leading Industries</div>
                    <p style="opacity: 0.7; margin-bottom: 25px;">Sectors showing extreme relative strength vs Nifty 50.</p>
    """
    
    for i, sec in enumerate(top_secs[:5], 1):
        rs_val = sec.get("rs", 1.0)
        progress = min(100, max(0, (rs_val - 0.9) * 200)) # Scale for visual
        html += f"""
                    <div class="leader-item">
                        <div class="rank-number">{i}</div>
                        <div style="flex-grow: 1;">
                            <div class="industry-name">{sec['sector'].replace('Nifty ', '')}</div>
                            <div class="industry-rs">Relative Strength: {rs_val:.3f}</div>
                            <div class="progress-container">
                                <div class="progress-bar" style="width: {progress}%"></div>
                            </div>
                        </div>
                    </div>
        """
        
    html += """
                </div>
                <div class="card">
                    <div class="section-title">⚠️ Legging Industries</div>
                    <p style="opacity: 0.7; margin-bottom: 25px;">Avoid these sectors as they are underperforming the benchmark.</p>
    """
    
    for sec in lagging_secs[:5]:
        html += f"""
                    <div class="laggard-item">
                        <span style="font-weight: 500;">{sec['sector'].replace('Nifty ', '')}</span>
                        <span style="color: var(--error); font-weight: 700;">Weak Momentum</span>
                    </div>
        """
        
    html += """
                </div>
            </div>

            <div class="card" style="margin-bottom: 50px; border-left: 5px solid var(--primary);">
                <div class="section-title">🛡️ Special Allocation: Defense & AI</div>
                <p class="info-text">Strategic tracking of our core growth themes.</p>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;">
    """
    
    for strategy, stocks in scan_data["special_focus"].items():
        html += f"""
                    <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 20px;">
                        <div style="font-weight: 700; margin-bottom: 10px; color: var(--primary);">{strategy.upper()}</div>
        """
        for s in stocks[:3]:
            html += f'<div style="font-size: 0.9rem; margin-bottom: 5px;">• {s["symbol"]} (RS: {s["rs"]:.2f})</div>'
        html += "</div>"
        
    html += """
                </div>
            </div>

            <div class="stocks-section">
                <div class="section-title">🎯 Top Sector Leaders & Stock Advice</div>
    """
    
    # Show Top 3 Sectors and their top stock
    for i, sec in enumerate(top_secs[:3], 1):
        thesis = fund_eng.get_sector_thesis(sec["sector"])
        picks = stock_picks.get(sec["sector"], [])
        if not picks: continue
        
        top_pick = picks[0] # Focus on the Rank 1 stock for the newsletter
        m = top_pick.get("metrics", {})
        
        html += f"""
                <div class="stock-card">
                    <div class="stock-header">
                        <h2 class="stock-title">RANK #{i} Sector: {sec['sector'].replace('Nifty ', '')}</h2>
                        <span style="font-weight: 800; opacity: 0.8;">{top_pick['symbol']}</span>
                    </div>
                    <div class="stock-metrics-grid">
                        <div class="metric-box">
                            <div class="metric-val">{m.get('sales_growth', 'N/A')}</div>
                            <div class="metric-label">Sales Growth</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-val">{m.get('profit_growth', 'N/A')}</div>
                            <div class="metric-label">Profit Growth</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-val">{m.get('roe', 'N/A')}</div>
                            <div class="metric-label">ROE / ROCE</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-val">{m.get('debt_to_equity', 'N/A')}</div>
                            <div class="metric-label">Debt / Equity</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-val">{m.get('risk', 'N/A')}</div>
                            <div class="metric-label">Risk Rating</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-val" style="color: var(--success);">{sec['rs']:.2f}</div>
                            <div class="metric-label">RS Multiplier</div>
                        </div>
                    </div>
                    <div class="stock-content">
                        <div class="info-row">
                            <span class="info-label">📍 Government Policy & Industry Context</span>
                            <span class="info-text">{thesis.get('policy', 'Strong government push for domestic manufacturing and digitalization.')}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">✅ Why to Buy?</span>
                            <span class="info-text">{m.get('why_to_buy', 'Institutional accumulation and clear technical breakout.')}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">🔮 Future Perspective</span>
                            <span class="info-text">{m.get('future_perspective', 'Multi-year growth visibility due to order book expansion.')}</span>
                        </div>
                        <div style="margin-top: 30px; display: flex; gap: 10px;">
                            {' '.join([f'<span style="padding: 5px 12px; background: rgba(255,255,255,0.05); border-radius: 8px; font-size: 0.8rem;">#{p["symbol"]}</span>' for p in picks[1:4]])}
                        </div>
                    </div>
                </div>
        """

    html += f"""
            </div>

            <div class="footer">
                <p>{SYSTEM_NAME} Intelligence © 2026</p>
                <p>Disclaimer: This is for educational purposes. We are not SEBI registered advisors. Trading involves risk.</p>
                <p>Generated on {datetime.now(IST).strftime("%d %b %Y %H:%M:%S IST")}</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def save_newsletter_to_file(html_content, newsletter_type):
    """Saves the newsletter as an HTML file for distribution."""
    timestamp = datetime.now(IST).strftime("%Y%m%d_%H%M")
    filename = f"DR_SAAB_ADVICE_{newsletter_type}_{timestamp}.html"
    
    # Path relative to project root
    rel_path = f"reports/newsletters/{filename}"
    abs_path = os.path.join(os.getcwd(), rel_path)
    
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return abs_path

def push_newsletter_to_telegram(newsletter_obj):
    """Sends the newsletter notification and the file to Telegram."""
    log_terminal("[NEWSLETTER] Pushing to Telegram...", "INFO")
    
    # 1. Send text summary with URL
    send_telegram_msg(newsletter_obj["text"])
    
    # 2. Also send the actual HTML file as a document (as backup)
    token = db.get_param('telegram_bot_token')
    chat_id = db.get_param('telegram_chat_id')
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        files = {'document': open(newsletter_obj["filepath"], 'rb')}
        payload = {
            'chat_id': chat_id,
            'caption': f"📂 Backup File: {newsletter_obj['type']} Strategic Advice"
        }
        try:
            import requests
            requests.post(url, data=payload, files=files, timeout=30)
        except Exception as e:
            log_terminal(f"Telegram File Error: {e}", "ERROR")

def post_to_twitter(newsletter_obj):
    """
    Automate posting to Twitter (X).
    """
    import tweepy
    log_terminal("[NEWSLETTER] Posting to Twitter...", "INFO")
    
    api_key = db.get_param('twitter_api_key')
    api_secret = db.get_param('twitter_api_secret')
    access_token = db.get_param('twitter_access_token')
    access_secret = db.get_param('twitter_access_secret')
    
    if not all([api_key, api_secret, access_token, access_secret]):
        log_terminal("Twitter API keys missing. Skipping tweet.", "ALERT")
        return

    try:
        client = tweepy.Client(
            consumer_key=api_key, consumer_secret=api_secret,
            access_token=access_token, access_token_secret=access_secret
        )
        
        tweet_text = f"🚀 {SYSTEM_NAME} - {newsletter_obj['type']} Update\n\n"
        tweet_text += f"Leading Sectors: {', '.join([s['sector'].replace('Nifty ', '') for s in newsletter_obj['data']['top_sectors'][:2]])}\n"
        tweet_text += f"Defense Leader: {newsletter_obj['data']['special_focus']['Defense Strategy'][0]['symbol']}\n\n"
        tweet_text += f"Read the full professional report here:\n{newsletter_obj['url']}\n\n"
        tweet_text += "#StockMarketIndia #AlgoTrading #DrSaabAdvice"
        
        client.create_tweet(text=tweet_text)
        log_terminal("Tweet posted successfully!", "INFO")
    except Exception as e:
        log_terminal(f"Twitter Error: {e}", "ERROR")

if __name__ == "__main__":
    # Test generation
    report = generate_newsletter_content("DAILY")
    # push_newsletter_to_telegram(report)
    # post_to_twitter(report)
    print(f"Report generated at: {report['filepath']}")
    print(f"Public URL: {report['url']}")
