"""
Real-Time Market Clock Daemon & Live Execution Loop
Monitors NSE trading hours, triggers 3:15 PM BTST Scan, and monitors 9:15 AM Next-Day Exit.
"""

import time
import datetime
import pytz
from automation_engine import run_daily_automation
from btst_screener import scan_btst_opportunities

IST = pytz.timezone("Asia/Kolkata") if "pytz" in globals() else None

def get_ist_time():
    # Return local Indian Standard Time
    now = datetime.datetime.now()
    return now

def is_market_open_today():
    today = datetime.date.today()
    # Check weekday (0 = Monday, ..., 4 = Friday, 5 = Saturday, 6 = Sunday)
    if today.weekday() >= 5:
        return False
    return True

def start_live_daemon():
    print("================================================================================")
    print("  NSE REAL-TIME BTST DAEMON ACTIVATED")
    print("  Monitoring Indian Market Trading Sessions (Mon-Fri 09:15 to 15:30 IST)")
    print("================================================================================\n")

    scan_triggered_today = False
    exit_alerted_today = False

    while True:
        now = datetime.datetime.now()
        current_time_str = now.strftime("%H:%M:%S")
        weekday = now.weekday()

        # If weekend, sleep longer
        if weekday >= 5:
            print(f"[{current_time_str}] Weekend (Markets Closed). Sleeping 1 hour...")
            time.sleep(3600)
            continue

        current_hour = now.hour
        current_minute = now.minute

        # Reset daily trigger flags at midnight
        if current_hour == 0 and current_minute == 0:
            scan_triggered_today = False
            exit_alerted_today = False

        # --- 1. MORNING EXIT WINDOW: 09:15 AM - 09:30 AM ---
        if current_hour == 9 and 15 <= current_minute <= 30 and not exit_alerted_today:
            print(f"\n[🔔 {current_time_str}] MARKET OPENING: 9:15 AM EXIT WINDOW ACTIVATED!")
            print("Action: Check overnight BTST positions. Exit at Target (+25%) or cut by 9:30 AM.")
            exit_alerted_today = True

        # --- 2. EVENING SCAN WINDOW: 03:15 PM (15:15 IST) ---
        if current_hour == 15 and current_minute >= 15 and current_minute <= 25:
            if not scan_triggered_today:
                print(f"\n[🚀 {current_time_str}] 3:15 PM TRIGGER: Running Live BTST Institutional Screener...")
                try:
                    run_daily_automation()
                    scan_triggered_today = True
                    print("[✓] 3:15 PM Scan completed successfully. Orders alerted/logged.")
                except Exception as e:
                    print(f"[!] Error running screener: {e}")
            else:
                # Already scanned for today
                pass

        # Sleep interval: 30 seconds during market hours, 5 minutes outside
        if 9 <= current_hour <= 15:
            time.sleep(30)
        else:
            time.sleep(300)

if __name__ == "__main__":
    start_live_daemon()
