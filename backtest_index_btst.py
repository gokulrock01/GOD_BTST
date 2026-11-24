"""
Quantitative Backtest: Nifty 50 & Bank Nifty Index BTST / STBT Strategy
Evaluates overnight gap-up / gap-down follow-through on Index Day-High / Day-Low closes.
Compares:
1. Naked ATM Option (Delta 0.50)
2. In-The-Money (ITM) Option (Delta 0.70)
3. Bull Call / Bear Put Spread (Theta-hedged)
4. Index Futures (Zero theta decay)
"""

import numpy as np
import pandas as pd
import yfinance as yf
import datetime
import warnings

warnings.filterwarnings("ignore")

INDICES = {
    "NIFTY 50": "^NSEI",
    "BANK NIFTY": "^NSEBANK"
}

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def backtest_index(name, symbol, start_date="2022-01-01"):
    df = yf.download(symbol, start=start_date, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['RSI'] = calculate_rsi(df['Close'], 14)

    df['DailyRange'] = df['High'] - df['Low']
    df['ClosePos'] = (df['Close'] - df['Low']) / (df['DailyRange'] + 1e-5)
    df['BodyPct'] = (df['Close'] - df['Open']) / df['Open'] * 100.0

    df['NextOpen'] = df['Open'].shift(-1)
    df['NextHigh'] = df['High'].shift(-1)
    df['NextLow'] = df['Low'].shift(-1)

    valid_df = df.dropna().copy()
    trades = []

    # Minimum body requirement (0.5% for Nifty, 0.8% for BankNifty)
    min_body = 0.5 if "NIFTY 50" in name else 0.8

    for i in range(len(valid_df) - 1):
        row = valid_df.iloc[i]
        next_row = valid_df.iloc[i + 1]

        entry = row['Close']
        next_open = next_row['NextOpen']
        if pd.isna(next_open) or entry == 0:
            continue

        # --- 1. BULLISH INDEX BTST (Call Setup) ---
        # 1. Close in top 10% of day's range (>= 0.90)
        # 2. Strong green body (BodyPct >= min_body)
        # 3. In uptrend: Close > EMA20 > EMA50
        # 4. RSI between 55 and 72
        is_bullish = (
            row['ClosePos'] >= 0.90 and
            row['BodyPct'] >= min_body and
            row['Close'] > row['EMA20'] > row['EMA50'] and
            55 <= row['RSI'] <= 72
        )

        if is_bullish:
            gap_pct = (next_open - entry) / entry * 100.0

            # 1. Index Futures Return (Zero Theta)
            fut_return = gap_pct - 0.03  # 0.03% friction

            # 2. Naked ATM Option (Delta 0.50, -6% overnight Theta decay, -1% friction)
            # Leverage for Nifty ATM is ~55x
            atm_opt_return = (gap_pct * 0.50 * 55.0) - 6.0 - 1.0

            # 3. ITM Option (Delta 0.72, -3.5% overnight Theta decay, -0.8% friction)
            # Leverage for Nifty ITM is ~35x
            itm_opt_return = (gap_pct * 0.72 * 35.0) - 3.5 - 0.8

            # 4. Bull Call Spread (Delta ~0.30 net, Theta decay cut to -1.5%)
            spread_return = (gap_pct * 0.35 * 45.0) - 1.5 - 1.0

            trades.append({
                "Index": name,
                "Date": str(valid_df.index[i].date()),
                "Type": "Bullish CE",
                "Gap_%": gap_pct,
                "Futures_%": fut_return,
                "ATM_Opt_%": max(atm_opt_return, -90.0),
                "ITM_Opt_%": max(itm_opt_return, -75.0),
                "Spread_%": max(spread_return, -50.0),
                "Gap_Win": gap_pct > 0.15,
                "ATM_Win": atm_opt_return > 0,
                "ITM_Win": itm_opt_return > 0,
                "Spread_Win": spread_return > 0
            })

        # --- 2. BEARISH INDEX STBT (Put Setup) ---
        # 1. Close in bottom 10% of day's range (<= 0.10)
        # 2. Strong red body (BodyPct <= -min_body)
        # 3. In downtrend: Close < EMA20 < EMA50
        # 4. RSI between 28 and 45
        is_bearish = (
            row['ClosePos'] <= 0.10 and
            row['BodyPct'] <= -min_body and
            row['Close'] < row['EMA20'] < row['EMA50'] and
            28 <= row['RSI'] <= 45
        )

        if is_bearish:
            gap_pct = (entry - next_open) / entry * 100.0  # Positive if gaps down

            fut_return = gap_pct - 0.03
            atm_opt_return = (gap_pct * 0.50 * 55.0) - 6.0 - 1.0
            itm_opt_return = (gap_pct * 0.72 * 35.0) - 3.5 - 0.8
            spread_return = (gap_pct * 0.35 * 45.0) - 1.5 - 1.0

            trades.append({
                "Index": name,
                "Date": str(valid_df.index[i].date()),
                "Type": "Bearish PE",
                "Gap_%": gap_pct,
                "Futures_%": fut_return,
                "ATM_Opt_%": max(atm_opt_return, -90.0),
                "ITM_Opt_%": max(itm_opt_return, -75.0),
                "Spread_%": max(spread_return, -50.0),
                "Gap_Win": gap_pct > 0.15,
                "ATM_Win": atm_opt_return > 0,
                "ITM_Win": itm_opt_return > 0,
                "Spread_Win": spread_return > 0
            })

    tdf = pd.DataFrame(trades)
    return tdf

def run_all():
    print("================================================================================")
    print("  INDEX BTST / STBT QUANTITATIVE BACKTEST (NIFTY 50 & BANK NIFTY)")
    print("  Period: 2022 to Present | Cash-Settled Index Options")
    print("================================================================================\n")

    all_dfs = []
    for name, sym in INDICES.items():
        print(f"[*] Backtesting {name} ({sym})...")
        tdf = backtest_index(name, sym)
        all_dfs.append(tdf)
        
        n_trades = len(tdf)
        if n_trades == 0:
            continue
            
        gap_winrate = (len(tdf[tdf['Gap_Win'] == True]) / n_trades) * 100
        avg_gap = tdf['Gap_%'].mean()
        
        atm_winrate = (len(tdf[tdf['ATM_Win'] == True]) / n_trades) * 100
        atm_avg = tdf['ATM_Opt_%'].mean()
        
        itm_winrate = (len(tdf[tdf['ITM_Win'] == True]) / n_trades) * 100
        itm_avg = tdf['ITM_Opt_%'].mean()

        spd_winrate = (len(tdf[tdf['Spread_Win'] == True]) / n_trades) * 100
        spd_avg = tdf['Spread_%'].mean()
        
        fut_avg = tdf['Futures_%'].mean()
        fut_winrate = (len(tdf[tdf['Futures_%'] > 0]) / n_trades) * 100

        print(f"\n--- {name} Results ({n_trades} Trades) ---")
        print(f"  • Overnight Directional Gap-Up Rate : {gap_winrate:.1f}% (Avg Gap: {avg_gap:+.2f}%)")
        print(f"  • Index Futures / Cash Win Rate     : {fut_winrate:.1f}% (Avg Return: {fut_avg:+.2f}%)")
        print(f"  • Naked ATM Option Win Rate         : {atm_winrate:.1f}% (Avg Return: {atm_avg:+.2f}%)")
        print(f"  • In-The-Money (ITM) Option Win Rate : {itm_winrate:.1f}% (Avg Return: {itm_avg:+.2f}%)")
        print(f"  • Bull Call / Bear Put Spread Win   : {spd_winrate:.1f}% (Avg Return: {spd_avg:+.2f}%)\n")

    combined = pd.concat(all_dfs, ignore_index=True)
    total_n = len(combined)
    print("====================== COMBINED INDEX PERFORMANCE ======================")
    print(f"Total Index Setups Triggered        : {total_n}")
    print(f"Directional Gap Accuracy (>+0.15%)  : {(len(combined[combined['Gap_Win'] == True]) / total_n)*100:.1f}%")
    print(f"Futures / Delta-1 Win Rate          : {(len(combined[combined['Futures_%'] > 0]) / total_n)*100:.1f}%")
    print(f"Naked ATM Option Win Rate           : {(len(combined[combined['ATM_Win'] == True]) / total_n)*100:.1f}%")
    print(f"In-The-Money (ITM) Option Win Rate  : {(len(combined[combined['ITM_Win'] == True]) / total_n)*100:.1f}%")
    print(f"Theta-Hedged Spread Win Rate        : {(len(combined[combined['Spread_Win'] == True]) / total_n)*100:.1f}%")
    print("========================================================================\n")

if __name__ == "__main__":
    run_all()
