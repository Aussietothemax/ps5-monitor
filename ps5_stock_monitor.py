#!/usr/bin/env python3
"""
Watch the MTC Factory Outlet PS5 Digital (CFI-1x15B, no stand) listing and alert
the moment it comes back in stock.

Uses only the Python standard library. Run it with:

    python3 ps5_stock_monitor.py --ntfy-topic my-secret-ps5-topic

Alerts go out through:
  * ntfy.sh push notification to your phone (install the free "ntfy" app and
    subscribe to the same topic name). Pick a hard-to-guess topic name.
  * A desktop notification and sound (macOS / Linux / Windows).
  * Opening the product page in your browser.

Use --once to do a single check (handy for cron or GitHub Actions); in that
mode the exit code is 0 when in stock, 1 when out of stock, 2 on error.
"""

import argparse
import json
import os
import platform
import random
import re
import subprocess
import sys
import time
import urllib.request
import webbrowser
from datetime import datetime

PRODUCT_ID = 71424
PRODUCT_URL = ("https://mtcfactoryoutlet.com/product/"
               "playstation-5-ps5-digital-edition-console-cfi-1x15b-no-stand-included/")
API_URL = f"https://mtcfactoryoutlet.com/wp-json/wc/store/v1/products/{PRODUCT_ID}"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def check_api():
    """WooCommerce Store API: the cleanest signal. Returns (in_stock, detail)."""
    # Cache-buster so a CDN never hands back a stale "out of stock" answer.
    data = json.loads(fetch(f"{API_URL}?_={int(time.time())}"))
    in_stock = bool(data.get("is_in_stock")) and bool(data.get("is_purchasable", True))
    price = data.get("prices", {}).get("price")
    minor = data.get("prices", {}).get("currency_minor_unit", 2)
    price_str = f"${int(price) / 10 ** minor:.2f}" if price else "?"
    text = (data.get("stock_availability") or {}).get("text") or ""
    return in_stock, f"{text or ('In stock' if in_stock else 'Out of stock')} @ {price_str}"


def check_html():
    """Fallback: read the product page itself."""
    html = fetch(f"{PRODUCT_URL}?_={int(time.time())}")
    m = re.search(r'"availability"\s*:\s*"https?://schema\.org/(\w+)"', html)
    if m:
        status = m.group(1)
        return status in ("InStock", "LimitedAvailability", "OnlineOnly"), f"schema.org/{status}"
    if re.search(r'class="[^"]*\bstock\b[^"]*\bout-of-stock\b', html):
        return False, "out-of-stock badge"
    if 'name="add-to-cart"' in html:
        return True, "add-to-cart button present"
    raise RuntimeError("could not determine stock status from page HTML")


def check():
    try:
        return check_api()
    except Exception as e:
        log(f"API check failed ({e}); falling back to HTML")
        return check_html()


def notify(title, message, ntfy_topic=None, ntfy_server="https://ntfy.sh", open_browser=True):
    if ntfy_topic:
        try:
            req = urllib.request.Request(
                f"{ntfy_server.rstrip('/')}/{ntfy_topic}",
                data=message.encode("utf-8"),
                headers={
                    "Title": title,
                    "Priority": "urgent",
                    "Tags": "video_game,rotating_light",
                    "Click": PRODUCT_URL,
                    "Actions": f"view, Buy now, {PRODUCT_URL}",
                },
                method="POST",
            )
            urllib.request.urlopen(req, timeout=15).read()
            log(f"Push sent to ntfy topic '{ntfy_topic}'")
        except Exception as e:
            log(f"ntfy push failed: {e}")

    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["osascript", "-e",
                            f'display notification "{message}" with title "{title}" sound name "Glass"'],
                           check=False)
            subprocess.run(["say", title], check=False)
        elif system == "Linux":
            subprocess.run(["notify-send", "-u", "critical", title, message], check=False)
        elif system == "Windows":
            import winsound
            for _ in range(5):
                winsound.Beep(1000, 300)
    except Exception:
        pass
    print("\a" * 3, end="", flush=True)  # terminal bell

    if open_browser:
        try:
            webbrowser.open(PRODUCT_URL)
        except Exception:
            pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--interval", type=int, default=60,
                   help="seconds between checks (default 60; random jitter is added)")
    p.add_argument("--ntfy-topic", default=os.environ.get("NTFY_TOPIC"),
                   help="ntfy.sh topic for phone push alerts (or set NTFY_TOPIC)")
    p.add_argument("--ntfy-server", default=os.environ.get("NTFY_SERVER", "https://ntfy.sh"))
    p.add_argument("--no-browser", action="store_true", help="don't open the page when in stock")
    p.add_argument("--remind-every", type=int, default=300,
                   help="while still in stock, re-alert every N seconds (default 300, 0 = alert once)")
    p.add_argument("--once", action="store_true", help="check once and exit")
    p.add_argument("--duration", type=int, default=0,
                   help="stop watching after N seconds and exit 0 (for CI runs; default 0 = forever)")
    p.add_argument("--test-alert", action="store_true", help="send a test alert and exit")
    args = p.parse_args()

    if args.test_alert:
        notify("PS5 monitor test", "If you see this, alerts are working.",
               args.ntfy_topic, args.ntfy_server, open_browser=False)
        return 0

    if args.once:
        try:
            in_stock, detail = check()
        except Exception as e:
            log(f"Check failed: {e}")
            return 2
        log(f"{'IN STOCK' if in_stock else 'Out of stock'} - {detail}")
        if in_stock:
            notify("PS5 is IN STOCK at MTC!", f"{detail}. Tap to buy.",
                   args.ntfy_topic, args.ntfy_server, open_browser=not args.no_browser)
            return 0
        return 1

    log(f"Watching {PRODUCT_URL}")
    log(f"Interval ~{args.interval}s | ntfy topic: {args.ntfy_topic or '(none - desktop alerts only)'}")
    was_in_stock = False
    last_alert = 0.0
    failures = 0
    deadline = time.time() + args.duration if args.duration else None

    while deadline is None or time.time() < deadline:
        try:
            in_stock, detail = check()
            failures = 0
            if in_stock:
                now = time.time()
                if not was_in_stock or (args.remind_every and now - last_alert >= args.remind_every):
                    log(f"*** IN STOCK *** {detail}")
                    notify("PS5 is IN STOCK at MTC!", f"{detail}. Tap to buy.",
                           args.ntfy_topic, args.ntfy_server,
                           open_browser=not args.no_browser and not was_in_stock)
                    last_alert = now
                else:
                    log(f"Still in stock - {detail}")
            else:
                if was_in_stock:
                    log(f"Back to out of stock - {detail}")
                else:
                    log(f"Out of stock - {detail}")
            was_in_stock = in_stock
        except Exception as e:
            failures += 1
            log(f"Check failed ({failures} in a row): {e}")
            if failures == 10 and args.ntfy_topic:
                notify("PS5 monitor having trouble", f"10 failed checks in a row: {e}",
                       args.ntfy_topic, args.ntfy_server, open_browser=False)

        # Back off on repeated errors, plus jitter so we don't hammer the site.
        sleep_for = args.interval * min(2 ** max(failures - 1, 0), 10) if failures else args.interval
        sleep_for += random.uniform(0, max(5, args.interval * 0.2))
        if deadline is not None:
            remaining = deadline - time.time()
            if remaining <= sleep_for:
                break
        time.sleep(sleep_for)
    log("Done.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("Stopped.")
