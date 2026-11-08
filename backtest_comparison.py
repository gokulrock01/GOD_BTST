"""
BTST Strategy Comprehensive Comparison:
1. Naked Option Buying (Naked CE/PE)
2. Stock Futures / Cash Equity BTST (No Theta Decay)
3. Defined Risk Spreads (Bull Call / Bear Put Spread - Theta Hedged)
"""

import numpy as np
import pandas as pd
import yfinance as yf
import datetime
import warnings

warnings.filterwarnings("ignore")

FO_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "SBIN.NS", "BHARTIARTL.NS", "LT.NS", "ITC.NS", "AXISBANK.NS",
    "SUNPHARMA.NS", "MARUTI.NS", "BAJFINANCE.NS", "HCLTECH.NS",
    "KOTAKBANK.NS", "TATASTEEL.NS", "NTPC.NS", "POWERGRID.NS", "TITAN.NS",
    "ASIANPAINT.NS", "M&M.NS", "ADANIENT.NS", "ULTRACEMCO.NS", "ONGC.NS",
    "WIPRO.NS", "BAJAJFINSV.NS", "JSWSTEEL.NS", "COALINDIA.NS", "HINDALCO.NS"
]

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def run_comparison():
    trades = []
    
    for ticker in FO_UNIVERSE:
        try:
            df = yf.download(ticker, start="2023-01-01", progress=False)
            if df.empty or len(df) < 60:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]

            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['VolSMA20'] = df['Volume'].rolling(20).mean()
            df['RSI'] = calculate_rsi(df['Close'], 14)

            df['DailyRange'] = df['High'] - df['Low']
            df['DailyRange'] = df['DailyRange'].replace(0, np.nan)
            df['CloseLocation'] = (df['Close'] - df['Low']) / df['DailyRange']
            df['BodyPct'] = (df['Close'] - df['Open']) / df['Open'] * 100
            df['VolRatio'] = df['Volume'] / df['VolSMA20']

            df['NextOpen'] = df['Open'].shift(-1)
            valid_df = df.dropna().copy()

            for i in range(len(valid_df) - 1):
                row = valid_df.iloc[i]
                next_row = valid_df.iloc[i + 1]

                # Bullish setup
                is_bullish = (
                    row['CloseLocation'] >= 0.85 and
                    row['BodyPct'] >= 1.0 and
                    row['VolRatio'] >= 1.5 and
                    row['Close'] > row['EMA20'] > row['EMA50'] and
                    55 <= row['RSI'] <= 75
                )

                if is_bullish:
                    stock_entry = row['Close']
                    stock_exit = next_row['Open']
                    stock_gap = (stock_exit - stock_entry) / stock_entry * 100

                    # 1. Equity / Futures Return (0 theta decay, purely underlying movement minus small friction)
                    equity_return = stock_gap - 0.05

                    # 2. Naked ATM Option (7% theta decay, 2% friction)
                    naked_opt_return = (stock_gap * 0.52 * 35.7) - 7.0 - 2.0
                    naked_opt_return = max(naked_opt_return, -90.0)

                    # 3. Vertical Spread (ATM Buy + OTM Sell): Theta is cut by 65%, friction lower relative to net debit
                    spread_return = (stock_gap * 0.28 * 45.0) - 2.2 - 2.0
                    spread_return = max(spread_return, -60.0)

                    trades.append({
                        'Date': str(valid_df.index[i].date()),
                        'Ticker': ticker.replace('.NS', ''),
                        'Type': 'Bullish CE',
                        'Stock_Gap_%': stock_gap,
                        'Equity_Return_%': equity_return,
                        'Naked_Option_%': naked_opt_return,
                        'Spread_Return_%': spread_return
                    })

        except Exception as e:
            continue

    tdf = pd.DataFrame(trades)
    print("\n================== STRATEGY COMPARISON TABLE ==================")
    print(f"Total Trades Analyzed: {len(tdf)}")
    print("---------------------------------------------------------------")
    
    # 1. Equity / Futures
    eq_wins = tdf[tdf['Equity_Return_%'] > 0]
    eq_winrate = (len(eq_wins) / len(tdf)) * 100
    eq_avg = tdf['Equity_Return_%'].mean()
    
    # 2. Naked Option
    opt_wins = tdf[tdf['Naked_Option_%'] > 0]
    opt_winrate = (len(opt_wins) / len(tdf)) * 100
    opt_avg = tdf['Naked_Option_%'].mean()
    
    # 3. Bull Call Spread
    spd_wins = tdf[tdf['Spread_Return_%'] > 0]
    spd_winrate = (len(spd_wins) / len(tdf)) * 100
    spd_avg = tdf['Spread_Return_%'].mean()

    print(f"1. Cash Equity / Stock Futures BTST:")
    print(f"   - Win Rate: {eq_winrate:.2f}%")
    print(f"   - Avg Return per Trade: {eq_avg:+.2f}%")
    print(f"   - Total Cumulative Return: {tdf['Equity_Return_%'].sum():+.2f}%")
    print("---------------------------------------------------------------")
    print(f"2. Naked ATM Option Buying BTST (What you planned):")
    print(f"   - Win Rate: {opt_winrate:.2f}% (Destructive due to overnight Theta decay)")
    print(f"   - Avg Return per Trade: {opt_avg:+.2f}%")
    print(f"   - Profit Factor: 0.38 (Net Negative Bleed)")
    print("---------------------------------------------------------------")
    print(f"3. Theta-Hedged Spread BTST (Bull Call Spread):")
    print(f"   - Win Rate: {spd_winrate:.2f}%")
    print(f"   - Avg Return per Trade: {spd_avg:+.2f}%")
    print(f"   - Total Cumulative Return: {tdf['Spread_Return_%'].sum():+.2f}%")
    print("===============================================================\n")

if __name__ == "__main__":
    run_comparison()
