"""
GOD BTST — Automation Execution Engine
Integrates the Orderflow Screener, Telegram Dispatcher, and Signals Log.
Supports both:
  - 'scan' (3:15 PM IST): Screens F&O universe, identifies top setups, sends Telegram alert.
  - 'morning-exit' (9:15 AM IST): Alerts to lock in profits or cut before 9:30 AM.
"""

import os
import sys
import json
import argparse
import datetime
from btst_screener import scan_btst_opportunities
from telegram_notifier import send_telegram_message, format_btst_scan_alert, format_morning_exit_alert

SIGNALS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signals")
ORDERS_FILE = os.path.join(SIGNALS_DIR, "btst_orders_today.json")

def ensure_signals_dir():
    if not os.path.exists(SIGNALS_DIR):
        os.makedirs(SIGNALS_DIR)

def run_315pm_scan():
    ensure_signals_dir()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_str}] 🚀 Triggering 3:15 PM Institutional Orderflow BTST Screener...")

    bullish_signals, bearish_signals = scan_btst_opportunities()

    # Sort candidates by volume expansion & orderflow score
    def get_sort_key(s):
        try:
            vol = float(s["Vol_Ratio"].replace("x", ""))
            of = float(s["OF_Score"].split("/")[0])
            return of * vol
        except:
            return 1.0

    bullish_signals.sort(key=get_sort_key, reverse=True)
    bearish_signals.sort(key=get_sort_key, reverse=True)

    # Save today's top orders
    today_orders = bullish_signals[:2] + bearish_signals[:2]
    with open(ORDERS_FILE, "w") as f:
        json.dump(today_orders, f, indent=4)
    print(f"[+] Active setups saved to '{ORDERS_FILE}'")

    # Format and send Telegram Alert
    alert_html = format_btst_scan_alert(bullish_signals, bearish_signals)
    send_telegram_message(alert_html)

def run_915am_exit():
    ensure_signals_dir()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_str}] 🔔 Triggering 9:15 AM Market Opening Exit Monitor...")

    active_orders = []
    if os.path.exists(ORDERS_FILE):
        try:
            with open(ORDERS_FILE, "r") as f:
                active_orders = json.load(f)
        except Exception as e:
            print(f"[!] Error loading {ORDERS_FILE}: {e}")

    alert_html = format_morning_exit_alert(active_orders)
    send_telegram_message(alert_html)

def main():
    parser = argparse.ArgumentParser(description="GOD BTST Automation Engine")
    parser.add_argument("--mode", choices=["scan", "morning-exit"], default="scan",
                        help="Execution mode: 'scan' (3:15 PM) or 'morning-exit' (9:15 AM)")
    args = parser.parse_args()

    if args.mode == "scan":
        run_315pm_scan()
    elif args.mode == "morning-exit":
        run_915am_exit()

if __name__ == "__main__":
    main()
