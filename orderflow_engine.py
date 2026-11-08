"""
Orderflow & Institutional Volume Profiler for NSE F&O Stocks
Calculates Intraday VWAP, Cumulative Volume Delta (CVD), Power-Hour Volume Concentration,
and Institutional Footprint Scores for high-conviction BTST/STBT setups.
"""

import numpy as np
import pandas as pd
import yfinance as yf
import datetime
import warnings

warnings.filterwarnings("ignore")

def compute_orderflow_metrics(intraday_df):
    """
    Analyzes 5-minute intraday bars to compute institutional orderflow parameters.
    """
    if intraday_df.empty or len(intraday_df) < 10:
        return None

    df = intraday_df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    # Typical Price
    df['TP'] = (df['High'] + df['Low'] + df['Close']) / 3.0
    df['PV'] = df['TP'] * df['Volume']

    # 1. Intraday VWAP
    cum_pv = df['PV'].cumsum()
    cum_vol = df['Volume'].cumsum()
    df['VWAP'] = cum_pv / (cum_vol + 1e-9)

    # VWAP Standard Deviation Bands
    df['VWAP_Dev'] = (df['TP'] - df['VWAP']) ** 2
    vwap_std = np.sqrt((df['VWAP_Dev'] * df['Volume']).cumsum() / (cum_vol + 1e-9))
    df['VWAP_Upper1'] = df['VWAP'] + vwap_std
    df['VWAP_Upper2'] = df['VWAP'] + (2.0 * vwap_std)
    df['VWAP_Lower1'] = df['VWAP'] - vwap_std
    df['VWAP_Lower2'] = df['VWAP'] - (2.0 * vwap_std)

    # 2. Bar-by-Bar Orderflow Delta (Lee-Ready / Spread-Aggression Model)
    # Delta = Volume * ( (Close - Open) / (High - Low + eps) )
    bar_range = df['High'] - df['Low']
    bar_range = bar_range.replace(0, 1e-5)
    bar_direction = (df['Close'] - df['Open']) / bar_range
    df['Bar_Delta'] = df['Volume'] * bar_direction
    df['CVD'] = df['Bar_Delta'].cumsum()  # Cumulative Volume Delta

    # 3. Power Hour Volume (Last 45 minutes: 14:45 to 15:30 IST)
    # Check timestamps
    total_day_volume = df['Volume'].sum()
    if total_day_volume == 0:
        return None

    # Filter last 8 to 9 bars (approx last 40-45 mins of 5m bars)
    power_hour_bars = df.iloc[-9:]
    power_hour_volume = power_hour_bars['Volume'].sum()
    power_hour_vol_ratio = (power_hour_volume / total_day_volume) * 100.0
    power_hour_delta = power_hour_bars['Bar_Delta'].sum()

    # Current Price vs VWAP
    ltp = df['Close'].iloc[-1]
    final_vwap = df['VWAP'].iloc[-1]
    final_cvd = df['CVD'].iloc[-1]
    vwap_distance_pct = ((ltp - final_vwap) / final_vwap) * 100.0

    # 4. Institutional Orderflow Conviction Score (0 to 100)
    score = 50.0  # neutral base

    # Above VWAP boost (+15)
    if ltp > final_vwap:
        score += 15.0
        # Above +1 Std Dev (+10)
        if ltp > df['VWAP_Upper1'].iloc[-1]:
            score += 10.0
    else:
        score -= 15.0
        if ltp < df['VWAP_Lower1'].iloc[-1]:
            score -= 10.0

    # CVD direction boost (+15)
    if final_cvd > 0:
        score += 15.0
    else:
        score -= 15.0

    # Power hour volume concentration (Institutions stepping in late)
    # Normally 45 mins out of 375 min session is ~12% of time.
    # If volume > 25%, institutions are actively marking up/down prices
    if power_hour_vol_ratio >= 25.0:
        if power_hour_delta > 0:
            score += 10.0
        else:
            score -= 10.0

    return {
        "LTP": round(float(ltp), 2),
        "VWAP": round(float(final_vwap), 2),
        "VWAP_Distance_%": round(float(vwap_distance_pct), 2),
        "Total_Volume": int(total_day_volume),
        "Power_Hour_Vol_%": round(float(power_hour_vol_ratio), 1),
        "Power_Hour_Delta": int(power_hour_delta),
        "Final_CVD": int(final_cvd),
        "Orderflow_Score": round(float(np.clip(score, 0, 100)), 1),
        "Institutional_Bias": "AGGRESSIVE BUYING" if score >= 75 else ("AGGRESSIVE SELLING" if score <= 25 else "NEUTRAL/BALANCED")
    }

if __name__ == "__main__":
    ticker = "HDFCBANK.NS"
    print(f"Testing Orderflow & Volume Profiler on {ticker}...")
    df = yf.download(ticker, period="2d", interval="5m", progress=False)
    metrics = compute_orderflow_metrics(df)
    for k, v in metrics.items():
        print(f"  {k}: {v}")
