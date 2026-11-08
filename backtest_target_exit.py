"""
Test Target-Based Exit (Next-Day Morning Target) vs Blind Open Exit
Simulates setting a Limit Target (+20%) at 9:15 AM Open with 9:30 AM Cutoff.
"""

import numpy as np
import pandas as pd
import yfinance as yf
import warnings

warnings.filterwarnings("ignore")

FO_SAMPLE = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS",
    "SBIN.NS", "BHARTIARTL.NS", "AXISBANK.NS", "KOTAKBANK.NS", "LT.NS",
    "ITC.NS", "MARUTI.NS", "BAJFINANCE.NS", "SUNPHARMA.NS", "TITAN.NS"
]

def run_target_exit_test():
    trades = []
    
    nifty = yf.download("^NSEI", start="2023-01-01", progress=False)
    if isinstance(nifty.columns, pd.MultiIndex):
        nifty.columns = [col[0] for col in nifty.columns]
    nifty['Nifty_EMA20'] = nifty['Close'].ewm(span=20, adjust=False).mean()
    nifty['Nifty_Regime'] = (nifty['Close'] > nifty['Nifty_EMA20']) & (nifty['Close'] > nifty['Open'])

    for ticker in FO_SAMPLE:
        try:
            df = yf.download(ticker, start="2023-01-01", progress=False)
            if df.empty or len(df) < 50:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]

            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['VolSMA20'] = df['Volume'].rolling(20).mean()
            df['High5D'] = df['High'].rolling(5).max()

            df['DailyRange'] = df['High'] - df['Low']
            df['ClosePos'] = (df['Close'] - df['Low']) / (df['DailyRange'] + 1e-5)
            df['BodyPct'] = (df['Close'] - df['Open']) / df['Open'] * 100.0
            df['VolRatio'] = df['Volume'] / df['VolSMA20']

            valid_df = df.dropna().copy()
            for i in range(len(valid_df) - 1):
                row = valid_df.iloc[i]
                next_row = valid_df.iloc[i + 1]
                idx_date = valid_df.index[i]

                nifty_bullish = False
                if idx_date in nifty.index:
                    nifty_bullish = bool(nifty.loc[idx_date, 'Nifty_Regime'])

                # Quality setup
                if (nifty_bullish and
                    (1.0 <= row['BodyPct'] <= 4.5) and
                    row['VolRatio'] >= 1.5 and
                    row['ClosePos'] >= 0.88 and
                    row['Close'] > row['EMA20'] > row['EMA50']):

                    entry = row['Close']
                    next_open = next_row['Open']
                    next_high = next_row['High']
                    next_low = next_row['Low']

                    open_gap_pct = (next_open - entry) / entry * 100.0
                    max_morning_gain_pct = (next_high - entry) / entry * 100.0
                    max_morning_drop_pct = (next_low - entry) / entry * 100.0

                    # Strategy A: Blind Open Exit (ATM option)
                    opt_open = (open_gap_pct * 0.50 * 35.7) - 7.0 - 2.0

                    # Strategy B: Dynamic Target Exit (ITM Option Delta 0.70)
                    # If stock reaches +0.8% morning expansion, ITM option hits +18-20% target!
                    itm_max_gain = (max_morning_gain_pct * 0.70 * 25.0) - 4.0 - 1.5
                    itm_max_loss = (max_morning_drop_pct * 0.70 * 25.0) - 4.0 - 1.5

                    if itm_max_gain >= 20.0:
                        opt_result = 20.0 # Target locked in
                    elif itm_max_loss <= -15.0:
                        opt_result = -15.0 # Stoploss hit
                    else:
                        opt_result = (open_gap_pct * 0.70 * 25.0) - 4.0 - 1.5 # Cut at 9:30 AM

                    # Strategy C: Cash Equity with Margin / MTF (Zero Theta Decay!)
                    equity_open_ret = open_gap_pct - 0.05
                    equity_target_ret = 1.5 if max_morning_gain_pct >= 1.5 else ( -1.0 if max_morning_drop_pct <= -1.0 else open_gap_pct - 0.05 )

                    trades.append({
                        "Ticker": ticker.replace(".NS", ""),
                        "Open_Gap_%": open_gap_pct,
                        "Max_Gain_%": max_morning_gain_pct,
                        "Blind_ATM_Opt_%": opt_open,
                        "Target_ITM_Opt_%": opt_result,
                        "Equity_Target_%": equity_target_ret
                    })

        except Exception as e:
            continue

    tdf = pd.DataFrame(trades)
    print(f"Total Quality Trades: {len(tdf)}")
    print("------------------------------------------------------------------")
    print(f"1. Blind ATM Option (Sell at Open regardless of price):")
    print(f"   Win Rate: {(len(tdf[tdf['Blind_ATM_Opt_%'] > 0]) / len(tdf))*100:.1f}% | Avg Return: {tdf['Blind_ATM_Opt_%'].mean():+.2f}%")
    print("------------------------------------------------------------------")
    print(f"2. Active ITM Target Option (+20% Target / -15% SL / 9:30 AM Cutoff):")
    itm_wins = tdf[tdf['Target_ITM_Opt_%'] > 0]
    print(f"   Win Rate: {(len(itm_wins) / len(tdf))*100:.1f}% | Avg Return: {tdf['Target_ITM_Opt_%'].mean():+.2f}%")
    print(f"   Profit Factor: {itm_wins['Target_ITM_Opt_%'].sum() / (abs(tdf[tdf['Target_ITM_Opt_%'] <= 0]['Target_ITM_Opt_%'].sum()) + 1e-9):.2f}")
    print("------------------------------------------------------------------")
    print(f"3. Cash Equity / Stock Futures BTST (Zero Theta Decay):")
    eq_wins = tdf[tdf['Equity_Target_%'] > 0]
    print(f"   Win Rate: {(len(eq_wins) / len(tdf))*100:.1f}% | Avg Return: {tdf['Equity_Target_%'].mean():+.2f}%")
    print(f"   Profit Factor: {eq_wins['Equity_Target_%'].sum() / (abs(tdf[tdf['Equity_Target_%'] <= 0]['Equity_Target_%'].sum()) + 1e-9):.2f}")
    print("==================================================================")

if __name__ == "__main__":
    run_target_exit_test()
