"""
report_server.py — BHARAT ALGOVERSE | Static Report Hosting
=========================================================
A minimal Flask server to host the premium HTML newsletters.
Runs on port 8503 by default.
"""

from flask import Flask, send_from_directory, render_template_string
import os

app = Flask(__name__)
REPORTS_DIR = os.path.join(os.getcwd(), "reports", "newsletters")

@app.route('/')
def list_reports():
    """Lists all available reports."""
    if not os.path.exists(REPORTS_DIR):
        return "No reports generated yet."
    
    files = sorted([f for f in os.listdir(REPORTS_DIR) if f.endswith(".html")], reverse=True)
    
    html = """
    <html>
    <head>
        <title>Dr. Saab's Advice | Market Reports</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: sans-serif; padding: 40px; background: #f4f7f6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
            h1 { color: #1a73e8; }
            ul { list-style: none; padding: 0; }
            li { padding: 15px; border-bottom: 1px solid #eee; }
            a { text-decoration: none; color: #333; font-weight: bold; }
            a:hover { color: #1a73e8; }
            .date { font-size: 0.8rem; color: #888; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Dr. Saab's Strategic Reports</h1>
            <p>Select a report to view detailed market intelligence.</p>
            <ul>
    """
    for f in files:
        html += f'<li><a href="/view/{f}">{f.replace(".html", "").replace("_", " ")}</a></li>'
    
    html += "</ul></div></body></html>"
    return render_template_string(html)

@app.route('/view/<path:filename>')
def serve_report(filename):
    """Serves a specific HTML report."""
    return send_from_directory(REPORTS_DIR, filename)

if __name__ == "__main__":
    if not os.path.exists(REPORTS_DIR):
        os.makedirs(REPORTS_DIR, exist_ok=True)
    
    print(f"Starting Report Server on http://0.0.0.0:8503")
    app.run(host='0.0.0.0', port=8503)
