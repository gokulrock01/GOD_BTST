"""
Angel One SmartAPI Live Market Feed for Top 95 Liquid NSE F&O Stocks
Batches requests in chunks of 45 to comply with Angel One API limits,
fetching real-time institutional quotes in under 1 second.
"""

import os
import sys
import json
import requests

try:
    import pyotp
    from SmartApi import SmartConnect
    SMARTAPI_AVAILABLE = True
except Exception:
    SMARTAPI_AVAILABLE = False

# Load Top 95 Liquid F&O Tokens
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "angel_tokens_expanded.json")

def load_tokens():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return {}

ANGEL_NSE_TOKENS = load_tokens()
TOKEN_TO_SYMBOL = {v: k for k, v in ANGEL_NSE_TOKENS.items()}

def get_angel_credentials():
    """Reads credentials from env vars or from /Users/gokul/Downloads/GOD/config.py"""
    api_key = os.getenv("ANGEL_API_KEY")
    client_code = os.getenv("ANGEL_CLIENT_CODE")
    pin = os.getenv("ANGEL_PIN")
    totp_key = os.getenv("ANGEL_TOTP_KEY")

    if not api_key or not client_code:
        god_dir = "/Users/gokul/Downloads/GOD"
        if os.path.exists(os.path.join(god_dir, "config.py")):
            try:
                sys.path.insert(0, god_dir)
                import config as god_config
                api_key = getattr(god_config, "ANGEL_API_KEY", "")
                client_code = getattr(god_config, "ANGEL_CLIENT_CODE", "")
                pin = getattr(god_config, "ANGEL_PIN", "")
                totp_key = getattr(god_config, "ANGEL_TOTP_KEY", "")
            except Exception:
                pass

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
        return None
    except Exception as e:
        print(f"[!] Angel One Session Error: {e}")
        return None

def fetch_live_quotes_angel(smart_api=None):
    """
    Fetches real-time quotes for all 95 F&O stocks in batched requests (max 45 per batch).
    Returns: dict mapping symbol -> {ltp, open, high, low, volume, close}
    """
    if smart_api is None:
        smart_api = get_angel_session()
        if smart_api is None:
            return None

    tokens = load_tokens()
    if not tokens:
        return None

    token_list = list(tokens.values())
    live_quotes = {}
    chunk_size = 45

    try:
        for i in range(0, len(token_list), chunk_size):
            chunk = token_list[i:i + chunk_size]
            response = smart_api.getMarketData(mode="FULL", exchangeTokens={"NSE": chunk})
            if response.get("status") and response.get("data"):
                fetched = response["data"].get("fetched", [])
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
    quotes = fetch_live_quotes_angel()
    if quotes:
        print(f"✅ Successfully fetched live quotes for {len(quotes)} F&O stocks:")
        sample = ["RELIANCE", "HDFCBANK", "TRENT", "DIXON", "HAL", "BEL", "POLYCAB"]
        for sym in sample:
            if sym in quotes:
                q = quotes[sym]
                print(f"  {sym:10}: LTP={q['ltp']} | High={q['high']} | Low={q['low']} | Vol={q['volume']:,}")
