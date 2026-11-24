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
import pytz
import yfinance as yf
from btst_screener import scan_btst_opportunities
from index_btst_engine import evaluate_academic_index_btst, format_asymmetric_telegram_dispatch
from telegram_notifier import send_telegram_message, format_btst_scan_alert, format_morning_exit_alert

SIGNALS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "signals")
ORDERS_FILE = os.path.join(SIGNALS_DIR, "btst_orders_today.json")
LEDGER_FILE = os.path.join(SIGNALS_DIR, "paper_trades_ledger.csv")

def calculate_paper_exit_pnl(orders):
    """
    Computes simulated paper trading P&L upon next-morning open (9:15 AM).
    Fetches real market open prices and evaluates the quantitative payoff.
    """
    results = []
    symbol_map = {
        "NIFTY 50": "^NSEI",
        "BANK NIFTY": "^NSEBANK",
        "SENSEX": "^BSESN"
    }

    for o in orders:
        name = o.get("Index") or o.get("Symbol")
        if not name:
            continue
        ticker_sym = symbol_map.get(name, f"{name}.NS")
        entry_spot = o.get("Spot_LTP") or o.get("LTP")

        try:
            ticker = yf.Ticker(ticker_sym)
            df = ticker.history(period="2d", interval="1d")
            if df.empty:
                continue
            open_price = float(df["Open"].iloc[-1])
            gap_pct = ((open_price - entry_spot) / entry_spot) * 100 if entry_spot else 0.0

            strat = o.get("Strategy", "")
            if "Bullish BWB" in strat:
                if 0.4 <= gap_pct <= 1.0:
                    pnl_pct = 50.0
                    notes = f"Target zone reached (+{gap_pct:.2f}% gap). Max sweet-spot booked!"
                elif gap_pct > 1.0:
                    pnl_pct = 25.0
                    notes = f"Large gap up (+{gap_pct:.2f}%). Deep ITM wing profit secured."
                elif 0.0 <= gap_pct < 0.4:
                    pnl_pct = 10.0
                    notes = f"Flat/mild open (+{gap_pct:.2f}%). Captured 2x short OTM decay."
                else:
                    pnl_pct = -6.5
                    notes = f"Gap against ({gap_pct:.2f}%). Downside strictly capped by wing hedge."
            elif "Bearish BWB" in strat:
                if -1.0 <= gap_pct <= -0.4:
                    pnl_pct = 50.0
                    notes = f"Target zone reached ({gap_pct:.2f}% gap). Max sweet-spot booked!"
                elif gap_pct < -1.0:
                    pnl_pct = 25.0
                    notes = f"Large gap down ({gap_pct:.2f}%). Deep ITM wing profit secured."
                elif -0.4 < gap_pct <= 0.0:
                    pnl_pct = 10.0
                    notes = f"Flat/mild open ({gap_pct:.2f}%). Captured 2x short OTM decay."
                else:
                    pnl_pct = -6.5
                    notes = f"Gap against ({gap_pct:+.2f}%). Upside strictly capped by wing hedge."
            elif "IRON CONDOR" in strat:
                if -0.45 <= gap_pct <= 0.45:
                    pnl_pct = 30.0
                    notes = f"Contained in range ({gap_pct:+.2f}% gap). Full overnight Theta harvested!"
                else:
                    pnl_pct = -14.0
                    notes = f"Gap breached wings ({gap_pct:+.2f}%). Wing stop-loss triggered."
            else:
                pnl_pct = gap_pct * 3.0
                notes = f"Directional exit on open ({gap_pct:+.2f}% move)."

            results.append({
                "name": name,
                "strategy": strat,
                "entry_spot": round(entry_spot, 2) if entry_spot else 0.0,
                "open_spot": round(open_price, 2),
                "gap_pct": round(gap_pct, 2),
                "pnl_pct": round(pnl_pct, 1),
                "notes": notes
            })
        except Exception as e:
            print(f"[!] Error calculating PnL for {name}: {e}")

    # Log to CSV Ledger
    if results:
        file_exists = os.path.exists(LEDGER_FILE)
        now_dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(LEDGER_FILE, "a") as f:
            if not file_exists:
                f.write("Date,Instrument,Strategy,Entry_Spot,Open_Spot,Gap_Pct,PnL_Pct,Notes\n")
            for r in results:
                f.write(f'"{now_dt}","{r["name"]}","{r["strategy"]}",{r["entry_spot"]},{r["open_spot"]},{r["gap_pct"]}%,{r["pnl_pct"]}%,\"{r["notes"]}\"\n')
        print(f"[+] Appended {len(results)} trade(s) to Paper Trading Ledger: '{LEDGER_FILE}'")

    return results

def is_market_day_today():
    """
    Checks if today is a regular NSE trading day.
    Returns (is_open: bool, reason: str)
    """
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.datetime.now(ist)
    today_str = now_ist.strftime("%Y-%m-%d")
    
    # Special Diwali Muhurat Trading Session Check
    if today_str == "2026-11-08":
        return True, "Diwali Muhurat Trading Session (Samvat 2083)"

    # 1. NSE Holiday Guard Check
    try:
        from nse_holiday_guard import is_market_open_today
        res = is_market_open_today(now_ist.date())
        is_open = res[0]
        h_reason = res[1] if len(res) > 1 else "Holiday"
        if not is_open:
            return False, h_reason
    except Exception as e:
        print(f"  ⚠️ Holiday check error: {e}")

    # 2. Weekend Check (5 = Saturday, 6 = Sunday)
    if now_ist.weekday() >= 5:
        return False, f"Weekend ({now_ist.strftime('%A')})"

    return True, "Active Trading Day"

def ensure_signals_dir():
    """Ensures the signals directory exists."""
    os.makedirs(SIGNALS_DIR, exist_ok=True)

def update_heartbeat(mode: str):
    """Updates heartbeat timestamp to prevent GitHub Actions cron auto-disable."""
    ensure_signals_dir()
    heartbeat_path = os.path.join(SIGNALS_DIR, "heartbeat.json")
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.datetime.now(ist)
    data = {
        "last_run_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "last_mode": mode,
        "status": "HEALTHY"
    }
    with open(heartbeat_path, "w") as f:
        json.dump(data, f, indent=4)

def run_315pm_scan(force=False, target="index"):
    update_heartbeat("scan")
    is_open, reason = is_market_day_today()
    if not is_open and not force:
        print(f"[i] Market is closed today: {reason}. Skipping scan.")
        return

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if target == "index":
        print(f"[{now_str}] 🚀 Triggering 3:15 PM Asymmetric Index BTST Sentinel (Nifty/BankNifty/Sensex)...")
        index_setups = evaluate_academic_index_btst()

        with open(ORDERS_FILE, "w") as f:
            json.dump(index_setups, f, indent=4)
        print(f"[+] Active Index setups saved to '{ORDERS_FILE}'")

        alert_html = format_asymmetric_telegram_dispatch(index_setups)
        send_telegram_message(alert_html)
        return

    print(f"[{now_str}] 🚀 Triggering 3:15 PM Institutional Orderflow Stock Screener...")
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

def run_915am_exit(force=False):
    update_heartbeat("morning-exit")
    is_open, reason = is_market_day_today()
    if not is_open and not force:
        print(f"[i] Market is closed today: {reason}. Skipping morning exit monitor.")
        return

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_str}] 🔔 Triggering 9:15 AM Market Opening Exit Monitor...")

    active_orders = []
    if os.path.exists(ORDERS_FILE):
        try:
            with open(ORDERS_FILE, "r") as f:
                active_orders = json.load(f)
        except Exception as e:
            print(f"[!] Error loading {ORDERS_FILE}: {e}")

    pnl_results = calculate_paper_exit_pnl(active_orders) if active_orders else []

    alert_html = format_morning_exit_alert(active_orders, pnl_results=pnl_results)
    send_telegram_message(alert_html)

def main():
    parser = argparse.ArgumentParser(description="GOD BTST Automation Engine")
    parser.add_argument("--mode", choices=["scan", "morning-exit"], default="scan",
                        help="Execution mode: 'scan' (3:15 PM) or 'morning-exit' (9:15 AM)")
    parser.add_argument("--target", choices=["index", "stock"], default="index",
                        help="Trading target: 'index' (Nifty/BankNifty/Sensex) or 'stock'")
    parser.add_argument("--force", action="store_true", default=False,
                        help="Force execution even if market is closed today")
    args = parser.parse_args()

    if args.mode == "scan":
        run_315pm_scan(force=args.force, target=args.target)
    elif args.mode == "morning-exit":
        run_915am_exit(force=args.force)

if __name__ == "__main__":
    main()
