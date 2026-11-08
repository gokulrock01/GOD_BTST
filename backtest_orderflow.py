"""
Orderflow-Enhanced BTST Backtester
Tests if filtering by Cumulative Volume Delta (CVD) and VWAP Expansion improves BTST Win Rates.
"""

import numpy as np
import pandas as pd
import yfinance as yf
import datetime
import warnings

warnings.filterwarnings("ignore")

FO_SAMPLE = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "SBIN.NS",
    "BHARTIARTL.NS", "LT.NS", "ITC.NS", "AXISBANK.NS", "MARUTI.NS"
]

def run_orderflow_backtest():
    print("================================================================================")
    print("  ORDERFLOW & VWAP BTST BACKTEST (INTRADAY 5-MIN BARS)")
    print("================================================================================\n")

    trades_standard = []
    trades_orderflow = []

    for ticker in FO_SAMPLE:
        try:
            # Download recent intraday 5m data (max available ~60 days on yfinance)
            df = yf.download(ticker, period="60d", interval="5m", progress=False)
            if df.empty or len(df) < 50:
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]

            # Group by trading date
            df['Date'] = df.index.date
            dates = df['Date'].unique()

            for i in range(len(dates) - 1):
                d_curr = dates[i]
                d_next = dates[i + 1]

                day_df = df[df['Date'] == d_curr].copy()
                next_day_df = df[df['Date'] == d_next].copy()

                if len(day_df) < 20 or next_day_df.empty:
                    continue

                day_open = day_df['Open'].iloc[0]
                day_high = day_df['High'].max()
                day_low = day_df['Low'].min()
                day_close = day_df['Close'].iloc[-1]
                day_vol = day_df['Volume'].sum()

                # Next day open
                next_open = next_day_df['Open'].iloc[0]
                gap_pct = (next_open - day_close) / day_close * 100.0

                # Standard Criteria
                day_range = day_high - day_low
                if day_range <= 0:
                    continue

                close_pos = (day_close - day_low) / day_range
                body_pct = (day_close - day_open) / day_open * 100.0

                is_standard_btst = (close_pos >= 0.85 and body_pct >= 0.8)

                if is_standard_btst:
                    trades_standard.append({
                        "Date": str(d_curr),
                        "Ticker": ticker.replace(".NS", ""),
                        "Gap_%": gap_pct,
                        "Win": gap_pct > 0.3  # Needs at least 0.3% gap to beat overnight option theta
                    })

                    # Orderflow criteria:
                    # 1. Intraday VWAP
                    cum_pv = (day_df['High'] + day_df['Low'] + day_df['Close']) / 3.0 * day_df['Volume']
                    vwap = cum_pv.sum() / (day_df['Volume'].sum() + 1e-9)

                    # 2. Cumulative Volume Delta (CVD)
                    bar_ranges = day_df['High'] - day_df['Low']
                    bar_ranges = bar_ranges.replace(0, 1e-5)
                    bar_deltas = day_df['Volume'] * ((day_df['Close'] - day_df['Open']) / bar_ranges)
                    cvd = bar_deltas.sum()

                    # 3. Power hour delta (last 45 mins)
                    power_hour_delta = bar_deltas.iloc[-9:].sum()

                    # Orderflow Confirmation: Price > VWAP and CVD strongly positive and late-day buying
                    is_orderflow_confirmed = (
                        day_close > vwap and
                        cvd > 0 and
                        power_hour_delta > 0
                    )

                    if is_orderflow_confirmed:
                        trades_orderflow.append({
                            "Date": str(d_curr),
                            "Ticker": ticker.replace(".NS", ""),
                            "Gap_%": gap_pct,
                            "Win": gap_pct > 0.3
                        })

        except Exception as e:
            continue

    df_std = pd.DataFrame(trades_standard)
    df_of = pd.DataFrame(trades_orderflow)

    print(f"Total Standard Setups Triggered   : {len(df_std)}")
    if not df_std.empty:
        std_winrate = (len(df_std[df_std['Win'] == True]) / len(df_std)) * 100
        print(f"Standard Setups Win Rate (>+0.3%): {std_winrate:.2f}%")
        print(f"Average Gap                       : {df_std['Gap_%'].mean():+.2f}%")

    print("\n---------------------------------------------------------------")
    print(f"Total Orderflow-Confirmed Setups  : {len(df_of)}")
    if not df_of.empty:
        of_winrate = (len(df_of[df_of['Win'] == True]) / len(df_of)) * 100
        print(f"Orderflow Confirmed Win Rate      : {of_winrate:.2f}%")
        print(f"Average Gap (Orderflow Confirmed) : {df_of['Gap_%'].mean():+.2f}%")
    print("===============================================================\n")

if __name__ == "__main__":
    run_orderflow_backtest()
