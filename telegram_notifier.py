"""
GOD BTST — TELEGRAM NOTIFICATION DISPATCHER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sends institutional-grade HTML alerts for:
  - 3:18 PM BTST High-Conviction Stock Options Calls (CE / PE)
  - Orderflow Delta, VWAP, and Volume Multipliers
  - 9:15 AM Morning Exit & Gap-Up Monitoring
  - Direct strike instructions and risk limits

Credentials read from environment variables:
  - TELEGRAM_BOT_TOKEN (or SWING_BOT_TOKEN)
  - TELEGRAM_CHAT_ID (or GOD_SWING_ID)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import requests
import datetime

BOT_TOKEN = os.getenv("BTST_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("SWING_BOT_TOKEN")
CHAT_ID   = os.getenv("BTST_ID") or os.getenv("TELEGRAM_CHAT_ID") or os.getenv("GOD_SWING_ID")

# Fallback to /Users/gokul/Downloads/GOD/config.py if running locally
if not BOT_TOKEN or not CHAT_ID:
    god_dir = "/Users/gokul/Downloads/GOD"
    if os.path.exists(os.path.join(god_dir, "config.py")):
        try:
            import sys
            if god_dir not in sys.path:
                sys.path.insert(0, god_dir)
            import config as god_config
            BOT_TOKEN = getattr(god_config, "TELEGRAM_BOT_TOKEN", BOT_TOKEN)
            CHAT_ID = getattr(god_config, "TELEGRAM_CHAT_ID", CHAT_ID)
        except Exception:
            pass

def send_telegram_message(message_html: str) -> bool:
    """Sends a rich HTML formatted message to Telegram."""
    if not BOT_TOKEN or not CHAT_ID:
        print("  ℹ️ Telegram credentials not configured in env. Skipping dispatch.")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("  ✅ Telegram notification dispatched successfully!")
            return True
        else:
            print(f"  ⚠️ Telegram API error ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        print(f"  ⚠️ Failed to send Telegram message: {e}")
        return False

def format_btst_scan_alert(bullish_setups, bearish_setups):
    """Formats an institutional Telegram alert for the 3:18 PM execution window."""
    now_str = datetime.datetime.now().strftime("%d-%b-%Y %H:%M IST")
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")

    is_muhurat = (today_date == "2026-11-08" or os.getenv("FORCE_MUHURAT", "").lower() in ["1", "true"])

    if is_muhurat:
        msg = "<b>🪔 GOD BTST — DIWALI MUHURAT TRADING 2026 (SAMVAT 2083) 🪔</b>\n"
        msg += f"<i>✨ Special Muhurat Trading Session Scan | {now_str} ✨</i>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    else:
        msg = "<b>⚡ GOD BTST — INSTITUTIONAL OPTIONS DISPATCH 🇮🇳</b>\n"
        msg += f"<i>NSE F&O | Orderflow & Volume Breakout | {now_str}</i>\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    total_setups = len(bullish_setups) + len(bearish_setups)

    if total_setups == 0:
        msg += "<b>💤 MARKET SUMMARY:</b>\n"
        msg += "• No setups met the strict institutional criteria today.\n"
        msg += "• <b>Action:</b> Zero trade. Capital protected from overnight Theta decay.\n"
        return msg

    msg += f"<b>🎯 CONFIRMED SIGNALS FOR OVERNIGHT CARRY:</b> ({total_setups} found)\n"
    msg += "<b>⏰ EXECUTION WINDOW:</b> <code>3:20 PM – 3:26 PM</code>\n\n"

    # Bullish (CE) trades
    if bullish_setups:
        for idx, s in enumerate(bullish_setups[:2], 1):
            msg += f"<b>🟢 #{idx} {s['Symbol']} — {s['Recommended_Option']}</b>\n"
            msg += f"• <b>LTP:</b> ₹{s['LTP']:,} (<code>{s['Range_%']}%</code> of Day High)\n"
            msg += f"• <b>VWAP:</b> ₹{s['VWAP']:,} (Trading above benchmark)\n"
            msg += f"• <b>Volume Expansion:</b> <code>{s['Vol_Ratio']}</code> 20-day SMA\n"
            msg += f"• <b>Orderflow Score:</b> <code>{s['OF_Score']}</code> (Institutional Accumulation)\n"
            msg += f"• <b>Power-Hour Delta:</b> <code>{s['Power_Hour_Delta']}</code> contracts\n"
            msg += f"• <b>Target Gain:</b> <code>+25% to +40%</code> at 9:15–9:30 AM Open\n"
            msg += f"• <b>Stop Loss:</b> <code>-15%</code> on Option Premium\n\n"

    # Bearish (PE) trades
    if bearish_setups:
        for idx, s in enumerate(bearish_setups[:2], 1):
            msg += f"<b>🔴 #{idx} {s['Symbol']} — {s['Recommended_Option']}</b>\n"
            msg += f"• <b>LTP:</b> ₹{s['LTP']:,} (<code>{s['Range_%']}%</code> of Day Low)\n"
            msg += f"• <b>VWAP:</b> ₹{s['VWAP']:,} (Trading below benchmark)\n"
            msg += f"• <b>Volume Expansion:</b> <code>{s['Vol_Ratio']}</code> 20-day SMA\n"
            msg += f"• <b>Orderflow Score:</b> <code>{s['OF_Score']}</code> (Institutional Distribution)\n"
            msg += f"• <b>Power-Hour Delta:</b> <code>{s['Power_Hour_Delta']}</code> contracts\n"
            msg += f"• <b>Target Gain:</b> <code>+25% to +40%</code> at 9:15–9:30 AM Open\n"
            msg += f"• <b>Stop Loss:</b> <code>-15%</code> on Option Premium\n\n"

    msg += "<b>🛡️ RISK & EXECUTION PLAYBOOK:</b>\n"
    msg += "1. <b>Expiry:</b> Current monthly expiry only (Never trade in monthly expiry week!).\n"
    msg += "2. <b>Hard Exit:</b> <b>9:15 AM – 9:30 AM tomorrow.</b> If stock opens flat, THETA WILL HURT. Dump by 9:30 AM.\n"
    msg += "3. <b>Position Size:</b> Max 1 or 2 lots per stock.\n"

    return msg

def format_morning_exit_alert(orders):
    """Formats 9:15 AM market opening notification to lock in profits."""
    now_str = datetime.datetime.now().strftime("%d-%b-%Y %H:%M IST")

    msg = "<b>🔔 GOD BTST — 9:15 AM MARKET OPENING ALERT 🇮🇳</b>\n"
    msg += f"<i>Time to monitor & exit overnight positions | {now_str}</i>\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if not orders:
        msg += "• No active overnight positions logged from yesterday.\n"
        return msg

    msg += "<b>📋 ACTIVE OVERNIGHT POSITIONS:</b>\n"
    for o in orders:
        msg += f"• <b>{o.get('Symbol')}</b>: <code>{o.get('Recommended_Option', 'ATM Option')}</code>\n"

    msg += "\n<b>🎯 9:15 AM PROFIT BOOKING CHECKLIST:</b>\n"
    msg += "• <b>Scenario A (Gap Up ≥ +0.8%):</b> Option premium jumps +20% to +45%. <b>Book 75% profit immediately!</b>\n"
    msg += "• <b>Scenario B (Flat Open 0.0% to +0.3%):</b> Theta decay is accelerating. Exit completely by <b>9:30 AM</b>.\n"
    msg += "• <b>Strict Rule:</b> Never hold a BTST naked option past 9:45 AM hoping for a late intraday recovery.\n"

    return msg

if __name__ == "__main__":
    test_bull = [{
        "Symbol": "HDFCBANK",
        "LTP": 788.25,
        "VWAP": 766.81,
        "Range_%": 100.0,
        "Vol_Ratio": "2.1x",
        "OF_Score": "90/100",
        "Power_Hour_Delta": "+3,524,426",
        "Recommended_Option": "BUY 790 CE"
    }]
    alert = format_btst_scan_alert(test_bull, [])
    print("Formatted Alert Preview:")
    print(alert)
