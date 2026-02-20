#!/usr/bin/env python3
"""
Presence monitor process
- Pings configured phone IPs at regular intervals
- Debounces per-device state (requires N consistent changes to flip)
- Logs state changes
- Serves current debounced state via a simple HTTP endpoint

Run this separately (or via systemd) alongside `main.py`.
"""
import json
import logging
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from datetime import datetime
import subprocess
from zoneinfo import ZoneInfo

import config

LOG = logging.getLogger("presence_monitor")
LOG.setLevel(logging.INFO)
# File handler
file_handler = logging.FileHandler(config.PRESENCE_LOG_FILE)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
LOG.addHandler(file_handler)
# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
LOG.addHandler(console_handler)

# In-memory state
state_lock = threading.Lock()
people_state = {name: {"is_home": True, "counter": 0, "last_changed": None} for name in config.PHONE_IPS}
# default to True (assume home) so first "nobody home" will trigger a check in main process

last_overall_change = None


def ping_host(ip: str) -> bool:
    try:
        result = subprocess.run(["ping", "-c", "1", "-W", "1", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        return result.returncode == 0
    except Exception:
        return False


class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/status":
            self.send_response(404)
            self.end_headers()
            return
        with state_lock:
            people = [name for name, info in people_state.items() if info["is_home"]]
            overall = len(people) > 0
            payload = {
                "someone_home": overall,
                "people_home": people,
                "last_changed": last_overall_change.isoformat() if last_overall_change else None,
                "per_person": {name: {"is_home": info["is_home"], "last_changed": info["last_changed"].isoformat() if info["last_changed"] else None} for name, info in people_state.items()}
            }
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        # suppress default logging to stdout
        return


def monitor_loop():
    global last_overall_change
    debounce = config.PRESENCE_DEBOUNCE
    interval = config.PRESENCE_PING_INTERVAL
    LOG.info("Monitor loop started")
    while True:
        any_change = False
        for name, ip in config.PHONE_IPS.items():
            ok = ping_host(ip)
            with state_lock:
                info = people_state[name]
                current = info["is_home"]
                if ok == current:
                    # reset counter
                    info["counter"] = 0
                else:
                    info["counter"] += 1
                    if info["counter"] >= debounce:
                        # flip state
                        info["is_home"] = ok
                        info["last_changed"] = datetime.now(ZoneInfo(config.LOCAL_TIMEZONE))
                        info["counter"] = 0
                        any_change = True
                        LOG.info(f"Presence change: {name} is_home={info['is_home']}")
        if any_change:
            with state_lock:
                people = [n for n, info in people_state.items() if info["is_home"]]
                last_overall_change = datetime.now(ZoneInfo(config.LOCAL_TIMEZONE))
                LOG.info(f"Overall presence: someone_home={len(people) > 0}, people={people}")
        time.sleep(interval)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    daemon_threads = True


def run_http_server():
    server_address = ("0.0.0.0", config.PRESENCE_API_PORT)
    httpd = ThreadedHTTPServer(server_address, StatusHandler)
    LOG.info(f"Presence HTTP server listening on http://{server_address[0]}:{server_address[1]}/status")
    httpd.serve_forever()


def main():
    LOG.info("Starting presence monitor")
    LOG.info(f"Ping interval: {config.PRESENCE_PING_INTERVAL}s, Debounce: {config.PRESENCE_DEBOUNCE} checks")
    LOG.info(f"Monitoring: {list(config.PHONE_IPS.keys())}")
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    run_http_server()


if __name__ == "__main__":
    main()
