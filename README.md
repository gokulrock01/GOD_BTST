# GOD BTST — Institutional Options & Orderflow Engine (NSE)

Automated Buy Today, Sell Tomorrow (BTST) / Sell Today, Buy Tomorrow (STBT) stock options trading system powered by **Intraday Orderflow, Cumulative Volume Delta (CVD), and VWAP Aggression**. Fully integrated with **Telegram Notifications** and **GitHub Actions**.

---

## ⚡ Architecture & Dual Execution Windows

```
┌────────────────────────────────────────────────────────────────────────┐
│                        DAILY AUTOMATION TIMELINE                       │
├──────────────────┬─────────────────────────────────────────────────────┤
│ 03:15 PM IST     │ 🚀 EOD SCANNER TRIGGERS                             │
│ (09:45 AM UTC)   │ • Analyzes 30 liquid F&O stocks with 5m Orderflow   │
│                  │ • Dispatches High-Conviction CE / PE Telegram Alert │
│                  │ • Execution Window: 3:20 PM – 3:26 PM               │
├──────────────────┼─────────────────────────────────────────────────────┤
│ 09:15 AM IST     │ 🔔 MARKET OPENING EXIT MONITOR                      │
│ (03:45 AM UTC)   │ • Evaluates overnight gap                           │
│                  │ • Dispatches profit-booking alert (+25% to +40%)    │
│                  │ • Mandates exit before 9:30 AM if momentum stalls   │
└──────────────────┴─────────────────────────────────────────────────────┘
```

---

## 📲 Telegram Integration & Alerts

The Telegram notification engine in [`telegram_notifier.py`](file:///Users/gokul/Downloads/GOD_BTST/telegram_notifier.py) uses the exact HTML formatting established in your swing trading system.

### Environment Secrets:
The engine automatically reads:
* `TELEGRAM_BOT_TOKEN` (or fallback `SWING_BOT_TOKEN`)
* `TELEGRAM_CHAT_ID` (or fallback `GOD_SWING_ID`)

### Sample Telegram Alert Dispatched:
```text
⚡ GOD BTST — INSTITUTIONAL OPTIONS DISPATCH 🇮🇳
NSE F&O | Orderflow & Volume Breakout | 08-Nov-2026 15:18 IST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 CONFIRMED SIGNALS FOR OVERNIGHT CARRY: (2 found)
⏰ EXECUTION WINDOW: 3:20 PM – 3:26 PM

🟢 #1 HDFCBANK — BUY 790 CE
• LTP: ₹788.25 (100.0% of Day High)
• VWAP: ₹766.81 (Trading above benchmark)
• Volume Expansion: 2.1x 20-day SMA
• Orderflow Score: 90/100 (Institutional Accumulation)
• Power-Hour Delta: +3,524,426 contracts
• Target Gain: +25% to +40% at 9:15–9:30 AM Open
• Stop Loss: -15% on Option Premium

🛡️ RISK & EXECUTION PLAYBOOK:
1. Expiry: Current monthly expiry only (Never trade in monthly expiry week!).
2. Hard Exit: 9:15 AM – 9:30 AM tomorrow. If stock opens flat, THETA WILL HURT. Dump by 9:30 AM.
3. Position Size: Max 1 or 2 lots per stock.
```

---

## ⚙️ GitHub Actions Automation Setup

A workflow is configured in [`.github/workflows/btst_trader.yml`](file:///Users/gokul/Downloads/GOD_BTST/.github/workflows/btst_trader.yml):

1. **Scheduled Runs (Mon–Fri):**
   * `45 9 * * 1-5`: Runs at **3:15 PM IST** (09:45 UTC).
   * `45 3 * * 1-5`: Runs at **9:15 AM IST** (03:45 UTC).
2. **Manual Dispatch:**
   * Go to **GitHub Repo -> Actions -> Automated BTST Options Trader -> Run workflow**.
   * Select `scan` (for 3:15 PM scan) or `morning-exit` (for 9:15 AM exit).
3. **Repository Secrets Required:**
   Add these in **GitHub -> Settings -> Secrets and variables -> Actions**:
   * `TELEGRAM_BOT_TOKEN`
   * `TELEGRAM_CHAT_ID`

---

## 🛠️ Local Usage

### Run 3:15 PM Scan Manually:
```bash
python3 automation_engine.py --mode scan
```

### Run 9:15 AM Exit Alert Manually:
```bash
python3 automation_engine.py --mode morning-exit
```

### Run Multi-Year Historical Backtest:
```bash
python3 backtest_btst.py
```
