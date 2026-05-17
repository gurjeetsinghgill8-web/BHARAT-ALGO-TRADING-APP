"""
NSL_TUNNEL.py — NIFTY SUPER LEAGUE
====================================
Starts an SSH SOCKS5 tunnel to the Hetzner VPS (46.224.133.16).
This routes ALL Upstox API traffic through the registered static IP.

Tunnel: localhost:1080  →  VPS (46.224.133.16)  →  Upstox API

Run this BEFORE starting the engine. It stays alive in background.
"""

import subprocess
import sys
import os
import time
import requests

VPS_IP   = "46.224.133.16"
VPS_USER = "root"
SSH_KEY  = os.path.join(os.path.expanduser("~"), ".ssh", "id_rsa")
LOCAL_PORT = 1080

def is_tunnel_alive():
    try:
        resp = requests.get(
            "https://api.ipify.org",
            proxies={"https": f"socks5h://127.0.0.1:{LOCAL_PORT}"},
            timeout=5
        )
        ip = resp.text.strip()
        return ip == VPS_IP, ip
    except:
        return False, "unreachable"

def start_tunnel():
    print("=" * 55)
    print("  NSL TUNNEL — Starting SSH SOCKS5 Proxy")
    print(f"  VPS: {VPS_IP} | Local port: {LOCAL_PORT}")
    print("=" * 55)

    cmd = [
        "ssh",
        "-i", SSH_KEY,
        "-N",                          # No remote commands
        "-D", str(LOCAL_PORT),         # SOCKS5 dynamic port
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=5",
        "-o", "ExitOnForwardFailure=yes",
        f"{VPS_USER}@{VPS_IP}"
    ]

    print(f"\nStarting tunnel... (this window must stay open)")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Wait for tunnel to come up
    for i in range(10):
        time.sleep(2)
        alive, current_ip = is_tunnel_alive()
        if alive:
            print(f"\n  TUNNEL ACTIVE! Traffic going through: {current_ip}")
            print(f"  Proxy: socks5h://127.0.0.1:{LOCAL_PORT}")
            print("\n  Keep this window open.")
            print("  Now start: START.bat\n")

            # Save proxy to secrets.toml
            _save_proxy_to_secrets()
            return proc
        print(f"  Waiting for tunnel... ({i+1}/10)")

    print("\nTunnel may still be starting. Check with: python NSL_TUNNEL.py --check")
    return proc

def _save_proxy_to_secrets():
    import re
    toml = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".streamlit", "secrets.toml")
    proxy_val = f"socks5h://127.0.0.1:{LOCAL_PORT}"
    if os.path.exists(toml):
        with open(toml, "r") as f: content = f.read()
        new_line = f'UPSTOX_PROXY = "{proxy_val}"'
        if re.search(r"(?im)^UPSTOX_PROXY\s*=", content):
            content = re.sub(r"(?im)^UPSTOX_PROXY\s*=.*$", new_line, content)
        else:
            content += f"\n{new_line}\n"
        with open(toml, "w") as f: f.write(content)
        print(f"  Saved proxy to secrets.toml: {proxy_val}")

    # Also save to NSL DB
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import nsl_db as db
    db.set("upstox_proxy", proxy_val)
    print(f"  Saved proxy to nsl_trader.db")

if __name__ == "__main__":
    if "--check" in sys.argv:
        alive, ip = is_tunnel_alive()
        if alive:
            print(f"TUNNEL OK — IP: {ip}")
        else:
            print(f"TUNNEL DOWN — Current IP: {ip}")
        sys.exit(0)

    proc = start_tunnel()
    if proc:
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            print("\nTunnel stopped.")
