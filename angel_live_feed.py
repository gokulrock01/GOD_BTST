"""
Angel One SmartAPI Live Market Feed for Indian F&O Stocks
Connects directly to Angel One's institutional NSE WebSocket & REST API to fetch real-time
LTP, Day High, Day Low, and Traded Volume for top F&O stocks.
"""

import os
import sys
import json
import requests

try:
    import pyotp
    from SmartApi import SmartConnect
    SMARTAPI_AVAILABLE = True
except Exception as e:
    SMARTAPI_AVAILABLE = False

# Top F&O Stocks Angel One NSE Token Mapping
ANGEL_NSE_TOKENS = {
    "RELIANCE": "2885",
    "TCS": "11536",
    "HDFCBANK": "1333",
    "ICICIBANK": "4963",
    "INFY": "1594",
    "SBIN": "3045",
    "BHARTIARTL": "10604",
    "LT": "11483",
    "ITC": "1660",
    "AXISBANK": "5900",
    "MARUTI": "10999",
    "BAJFINANCE": "317",
    "HCLTECH": "7229",
    "KOTAKBANK": "1922",
    "TATASTEEL": "3499",
    "NTPC": "11630",
    "POWERGRID": "14977",
    "TITAN": "3506",
    "ASIANPAINT": "236",
    "M&M": "2031",
    "ADANIENT": "25",
    "ULTRACEMCO": "11532",
    "ONGC": "2475",
    "WIPRO": "3787",
    "BAJAJFINSV": "16675",
    "JSWSTEEL": "11723",
    "COALINDIA": "20374",
    "HINDALCO": "1363",
    "SUNPHARMA": "3351"
}

TOKEN_TO_SYMBOL = {v: k for k, v in ANGEL_NSE_TOKENS.items()}

def get_angel_credentials():
    """Reads credentials from env vars or from /Users/gokul/Downloads/GOD/config.py"""
    api_key = os.getenv("ANGEL_API_KEY")
    client_code = os.getenv("ANGEL_CLIENT_CODE")
    pin = os.getenv("ANGEL_PIN")
    totp_key = os.getenv("ANGEL_TOTP_KEY")

    if not api_key or not client_code:
        # Check /Users/gokul/Downloads/GOD/config.py
        god_dir = "/Users/gokul/Downloads/GOD"
        if os.path.exists(os.path.join(god_dir, "config.py")):
            try:
                sys.path.insert(0, god_dir)
                import config as god_config
                api_key = getattr(god_config, "ANGEL_API_KEY", "")
                client_code = getattr(god_config, "ANGEL_CLIENT_CODE", "")
                pin = getattr(god_config, "ANGEL_PIN", "")
                totp_key = getattr(god_config, "ANGEL_TOTP_KEY", "")
            except Exception as e:
                print(f"[!] Warning reading GOD/config.py: {e}")

    return api_key, client_code, pin, totp_key

def get_angel_session():
    """Authenticates with Angel One SmartAPI using TOTP"""
    if not SMARTAPI_AVAILABLE:
        return None

    api_key, client_code, pin, totp_key = get_angel_credentials()
    if not api_key or not client_code or not pin or not totp_key:
        return None

    try:
        smart_api = SmartConnect(api_key=api_key)
        totp = pyotp.TOTP(totp_key).now()
        data = smart_api.generateSession(client_code, pin, totp)
        if data.get("status"):
            return smart_api
        else:
            print(f"[!] Angel One Authentication Failed: {data.get('message')}")
            return None
    except Exception as e:
        print(f"[!] Angel One Session Error: {e}")
        return None

def fetch_live_quotes_angel(smart_api=None):
    """
    Fetches real-time institutional quote feed for all 29 F&O stocks in a single request.
    Returns: dict mapping symbol -> {ltp, open, high, low, volume, close}
    """
    if smart_api is None:
        smart_api = get_angel_session()
        if smart_api is None:
            return None

    token_list = list(ANGEL_NSE_TOKENS.values())
    
    try:
        # Fetch FULL market depth & OHLC in a single batch call
        response = smart_api.getMarketData(mode="FULL", exchangeTokens={"NSE": token_list})
        if not response.get("status") or not response.get("data"):
            print(f"[!] Angel One getMarketData error: {response}")
            return None

        fetched = response["data"].get("fetched", [])
        live_quotes = {}
        for item in fetched:
            token = str(item.get("symbolToken"))
            sym = TOKEN_TO_SYMBOL.get(token)
            if not sym:
                continue

            live_quotes[sym] = {
                "symbol": sym,
                "ltp": float(item.get("ltp", 0)),
                "open": float(item.get("open", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "close": float(item.get("close", 0)),
                "volume": int(item.get("tradeVolume", 0)),
                "upper_circuit": float(item.get("upperCircuit", 0)),
                "lower_circuit": float(item.get("lowerCircuit", 0))
            }

        return live_quotes
    except Exception as e:
        print(f"[!] Error fetching Angel live quotes: {e}")
        return None

if __name__ == "__main__":
    print("[*] Connecting to Angel One Live Market Feed...")
    quotes = fetch_live_quotes_angel()
    if quotes:
        print(f"✅ Successfully fetched live quotes for {len(quotes)} F&O stocks:")
        for sym in ["RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "TCS"]:
            if sym in quotes:
                q = quotes[sym]
                print(f"  {sym}: LTP={q['ltp']} | High={q['high']} | Low={q['low']} | Vol={q['volume']:,}")
    else:
        print("❌ Failed to fetch live quotes from Angel One.")
