"""
High-Speed Bulk Orderflow & Volume BTST Screener for Indian Stock F&O
Expanded to Top 95 High-Momentum F&O Stocks (Large-Cap & Mid-Cap Leaders)
Integrates Angel One SmartAPI Live Feed with 5-minute Intraday Orderflow and CVD.
"""

import os
import json
import datetime
import numpy as np
import pandas as pd
import yfinance as yf
import warnings
from orderflow_engine import compute_orderflow_metrics
from angel_live_feed import fetch_live_quotes_angel, ANGEL_NSE_TOKENS

warnings.filterwarnings("ignore")

# Expanded Top 95 Liquid F&O Universe
FO_SYMBOLS = list(ANGEL_NSE_TOKENS.keys()) if ANGEL_NSE_TOKENS else [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "SBIN", "BHARTIARTL", "AXISBANK",
    "KOTAKBANK", "LT", "ITC", "MARUTI", "BAJFINANCE", "SUNPHARMA", "TITAN",
    "ULTRACEMCO", "M&M", "TATASTEEL", "POWERGRID", "NTPC", "HCLTECH", "ASIANPAINT", "COALINDIA",
    "BAJAJFINSV", "JSWSTEEL", "HINDALCO", "ONGC", "ADANIENT", "ADANIPORTS", "TRENT", "BEL",
    "HAL", "DIXON", "POLYCAB", "PERSISTENT", "COFORGE", "DLF", "TATAPOWER", "VEDL", "SIEMENS"
]

FO_STOCKS = [f"{s}.NS" for s in FO_SYMBOLS]

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def get_atm_strike(ticker_clean, ltp):
    """Calculates ATM strike based on standard NSE strike spacing rules."""
    if ltp >= 10000:
        interval = 100
    elif ltp >= 2500:
        interval = 50
    elif ltp >= 1000:
        interval = 20
    elif ltp >= 500:
        interval = 10
    elif ltp >= 200:
        interval = 5
    else:
        interval = 2.5
    atm_strike = round(ltp / interval) * interval
    return int(atm_strike) if atm_strike == int(atm_strike) else atm_strike

def scan_btst_opportunities():
    print("================================================================================")
    print("  INSTITUTIONAL ORDERFLOW & VOLUME BTST / STBT SCANNER (NSE F&O)")
    print(f"  Universe: Top {len(FO_STOCKS)} Liquid F&O Stocks | Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("================================================================================\n")

    # 1. Fetch Angel One SmartAPI live quotes for all 95 stocks
    print(f"[*] Connecting to Angel One SmartAPI for {len(FO_SYMBOLS)} F&O symbols...")
    live_angel_quotes = None
    try:
        live_angel_quotes = fetch_live_quotes_angel()
        if live_angel_quotes:
            print(f"  ⚡ Live Angel One SmartAPI feed active ({len(live_angel_quotes)} symbols connected) ✅")
        else:
            print("  ℹ️ Angel One live feed unavailable. Using fallback stream.")
    except Exception as e:
        print(f"  ℹ️ Angel One connection skipped: {e}. Using fallback stream.")

    # 2. Bulk download daily & 5m history
    print(f"[*] Bulk downloading historical bars & 5m Orderflow...")
    try:
        daily_bulk = yf.download(FO_STOCKS, period="3mo", interval="1d", group_by="ticker", progress=False)
        intra_bulk = yf.download(FO_STOCKS, period="2d", interval="5m", group_by="ticker", progress=False)
    except Exception as e:
        print(f"[!] History download error: {e}")
        return [], []

    bullish_signals = []
    bearish_signals = []

    for ticker in FO_STOCKS:
        try:
            ticker_clean = ticker.replace(".NS", "")
            
            # Extract daily history
            if ticker not in daily_bulk or daily_bulk[ticker].empty:
                continue
            df_daily = daily_bulk[ticker].dropna()
            if len(df_daily) < 30:
                continue

            # Prioritize Angel One Live Quotes for real-time precision
            if live_angel_quotes and ticker_clean in live_angel_quotes:
                aq = live_angel_quotes[ticker_clean]
                ltp = aq["ltp"]
                open_price = aq["open"] if aq["open"] > 0 else float(df_daily['Open'].iloc[-1])
                high_price = aq["high"] if aq["high"] > 0 else float(df_daily['High'].iloc[-1])
                low_price = aq["low"] if aq["low"] > 0 else float(df_daily['Low'].iloc[-1])
                volume = aq["volume"] if aq["volume"] > 0 else float(df_daily['Volume'].iloc[-1])
                data_source = "Angel One Live"
            else:
                ltp = float(df_daily['Close'].iloc[-1])
                open_price = float(df_daily['Open'].iloc[-1])
                high_price = float(df_daily['High'].iloc[-1])
                low_price = float(df_daily['Low'].iloc[-1])
                volume = float(df_daily['Volume'].iloc[-1])
                data_source = "Fallback Web"

            ema20 = float(df_daily['Close'].ewm(span=20, adjust=False).mean().iloc[-1])
            ema50 = float(df_daily['Close'].ewm(span=50, adjust=False).mean().iloc[-1])
            vol_sma = float(df_daily['Volume'].rolling(20).mean().iloc[-1])
            rsi = float(calculate_rsi(df_daily['Close'], 14).iloc[-1])

            daily_range = high_price - low_price
            if daily_range <= 0:
                continue

            close_position = (ltp - low_price) / daily_range
            pct_change = ((ltp - open_price) / open_price) * 100
            vol_ratio = volume / vol_sma if vol_sma > 0 else 1.0

            # Intraday 5m Orderflow calculation
            if ticker not in intra_bulk or intra_bulk[ticker].empty:
                continue
            df_intraday = intra_bulk[ticker].dropna()
            of_metrics = compute_orderflow_metrics(df_intraday)
            if not of_metrics:
                continue

            orderflow_score = of_metrics["Orderflow_Score"]
            cvd = of_metrics["Final_CVD"]
            vwap = of_metrics["VWAP"]
            power_hour_delta = of_metrics["Power_Hour_Delta"]
            atm_strike = get_atm_strike(ticker_clean, ltp)

            # --- BULLISH ORDERFLOW BTST (CE Strategy) ---
            if (close_position >= 0.85 and 
                pct_change >= 0.8 and 
                vol_ratio >= 1.25 and 
                ltp > ema20 > ema50 and 
                ltp > vwap and
                cvd > 0 and
                orderflow_score >= 70):

                bullish_signals.append({
                    "Symbol": ticker_clean,
                    "LTP": round(ltp, 2),
                    "VWAP": round(vwap, 2),
                    "Range_%": round(close_position * 100, 1),
                    "Change_%": round(pct_change, 2),
                    "Vol_Ratio": f"{vol_ratio:.1f}x",
                    "OF_Score": f"{orderflow_score:.0f}/100",
                    "Power_Hour_Delta": f"{power_hour_delta:+,}",
                    "Recommended_Option": f"BUY {atm_strike} CE",
                    "Entry_Window": "3:20 - 3:25 PM",
                    "Target_Exit": "9:15 - 9:30 AM (+25% to +40%)",
                    "Feed": data_source
                })

            # --- BEARISH ORDERFLOW STBT (PE Strategy) ---
            if (close_position <= 0.15 and 
                pct_change <= -0.8 and 
                vol_ratio >= 1.25 and 
                ltp < ema20 < ema50 and 
                ltp < vwap and
                cvd < 0 and
                orderflow_score <= 30):

                bearish_signals.append({
                    "Symbol": ticker_clean,
                    "LTP": round(ltp, 2),
                    "VWAP": round(vwap, 2),
                    "Range_%": round(close_position * 100, 1),
                    "Change_%": round(pct_change, 2),
                    "Vol_Ratio": f"{vol_ratio:.1f}x",
                    "OF_Score": f"{orderflow_score:.0f}/100",
                    "Power_Hour_Delta": f"{power_hour_delta:+,}",
                    "Recommended_Option": f"BUY {atm_strike} PE",
                    "Entry_Window": "3:20 - 3:25 PM",
                    "Target_Exit": "9:15 - 9:30 AM (+25% to +40%)",
                    "Feed": data_source
                })

        except Exception as e:
            continue

    print("--------------------------------------------------------------------------------")
    print(f"🎯 BULLISH ORDERFLOW BTST (CALL OPTIONS / CE): {len(bullish_signals)} found")
    print("--------------------------------------------------------------------------------")
    if bullish_signals:
        df_b = pd.DataFrame(bullish_signals)
        print(df_b.to_string(index=False))
    else:
        print(">> No stocks passed both Price Action AND Orderflow/CVD institutional filters.")

    print("\n--------------------------------------------------------------------------------")
    print(f"🎯 BEARISH ORDERFLOW STBT (PUT OPTIONS / PE): {len(bearish_signals)} found")
    print("--------------------------------------------------------------------------------")
    if bearish_signals:
        df_s = pd.DataFrame(bearish_signals)
        print(df_s.to_string(index=False))
    else:
        print(">> No stocks passed both Price Action AND Orderflow/CVD institutional filters.")

    return bullish_signals, bearish_signals

if __name__ == "__main__":
    scan_btst_opportunities()
