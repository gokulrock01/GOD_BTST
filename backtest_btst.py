"""
BTST Strategy Backtester (Stock CE & PE Options Simulation)
Evaluates Day-High / Day-Low Volume Breakout setups across top NSE F&O stocks.
"""

import numpy as np
import pandas as pd
import yfinance as yf
import datetime
import warnings

warnings.filterwarnings("ignore")

# Top Liquid F&O Universe (High option liquidity, lowest bid-ask spreads)
FO_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "SBIN.NS", "BHARTIARTL.NS", "LT.NS", "ITC.NS", "AXISBANK.NS",
    "TATAMOTORS.NS", "SUNPHARMA.NS", "MARUTI.NS", "BAJFINANCE.NS", "HCLTECH.NS",
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

def run_backtest(start_date="2023-01-01", end_date=None):
    if end_date is None:
        end_date = datetime.date.today().strftime("%Y-%m-%d")

    print(f"============================================================")
    print(f"  NSE BTST / STBT STOCK OPTIONS BACKTESTING ENGINE")
    print(f"  Period: {start_date} to {end_date} | Universe: {len(FO_UNIVERSE)} F&O Stocks")
    print(f"============================================================\n")

    trades = []

    for ticker in FO_UNIVERSE:
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if df.empty or len(df) < 60:
                continue

            # Flatten MultiIndex columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]

            # Indicators
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['VolSMA20'] = df['Volume'].rolling(20).mean()
            df['RSI'] = calculate_rsi(df['Close'], 14)

            # Daily metrics
            df['DailyRange'] = df['High'] - df['Low']
            # Avoid division by zero
            df['DailyRange'] = df['DailyRange'].replace(0, np.nan)
            
            # Position of close in the day's range [0 to 1]
            df['CloseLocation'] = (df['Close'] - df['Low']) / df['DailyRange']
            df['BodyPct'] = (df['Close'] - df['Open']) / df['Open'] * 100
            df['VolRatio'] = df['Volume'] / df['VolSMA20']

            # Next Day Open Return (BTST overnight gap)
            # Buy at Day T Close, Sell at Day T+1 Open
            df['NextOpen'] = df['Open'].shift(-1)
            df['NextHigh'] = df['High'].shift(-1)
            df['NextLow'] = df['Low'].shift(-1)
            df['NextClose'] = df['Close'].shift(-1)

            # Drop rows with NaN in needed columns
            valid_df = df.dropna().copy()

            for i in range(len(valid_df) - 1):
                row = valid_df.iloc[i]
                next_row = valid_df.iloc[i + 1]
                date_str = str(valid_df.index[i].date())

                # --- 1. BULLISH BTST (CE Strategy) ---
                # Criteria:
                # 1. Close in top 15% of day range (>= 0.85)
                # 2. Strong green candle (Body >= +1.0%)
                # 3. Volume > 1.5x 20-day average
                # 4. Trend: Above 20 EMA and 50 EMA
                # 5. RSI between 55 and 75
                is_bullish = (
                    row['CloseLocation'] >= 0.85 and
                    row['BodyPct'] >= 1.0 and
                    row['VolRatio'] >= 1.5 and
                    row['Close'] > row['EMA20'] > row['EMA50'] and
                    55 <= row['RSI'] <= 75
                )

                if is_bullish:
                    stock_entry = row['Close']
                    stock_exit_open = next_row['Open']
                    stock_gap_pct = (stock_exit_open - stock_entry) / stock_entry * 100

                    # Option Modeling:
                    # ATM Call Option is approx 2.8% of stock price
                    # Delta = 0.52 (slightly ITM / ATM)
                    # Overnight Theta Decay = 7.0% penalty on option value
                    # Slippage + STT/Charges = 2.0%
                    opt_leverage = 1.0 / 0.028  # ~35.7x leverage
                    opt_pct_from_delta = stock_gap_pct * 0.52 * opt_leverage
                    opt_return_open = opt_pct_from_delta - 7.0 - 2.0  # Net after theta & friction

                    # Cap maximum option loss at -90% (options can't go below 0)
                    opt_return_open = max(opt_return_open, -90.0)

                    trades.append({
                        'Date': date_str,
                        'Ticker': ticker.replace('.NS', ''),
                        'Type': 'CE (Bullish)',
                        'Stock_Entry': round(stock_entry, 2),
                        'Stock_Exit_Open': round(stock_exit_open, 2),
                        'Stock_Gap_%': round(stock_gap_pct, 2),
                        'Option_Est_Return_%': round(opt_return_open, 2),
                        'Win': opt_return_open > 0
                    })

                # --- 2. BEARISH BTST / STBT (PE Strategy) ---
                # Criteria:
                # 1. Close in bottom 15% of day range (<= 0.15)
                # 2. Strong red candle (Body <= -1.0%)
                # 3. Volume > 1.5x 20-day average
                # 4. Trend: Below 20 EMA and 50 EMA
                # 5. RSI between 25 and 45
                is_bearish = (
                    row['CloseLocation'] <= 0.15 and
                    row['BodyPct'] <= -1.0 and
                    row['VolRatio'] >= 1.5 and
                    row['Close'] < row['EMA20'] < row['EMA50'] and
                    25 <= row['RSI'] <= 45
                )

                if is_bearish:
                    stock_entry = row['Close']
                    stock_exit_open = next_row['Open']
                    # For PE, gap down is positive return
                    stock_gap_pct = (stock_entry - stock_exit_open) / stock_entry * 100

                    opt_leverage = 1.0 / 0.028
                    opt_pct_from_delta = stock_gap_pct * 0.52 * opt_leverage
                    opt_return_open = opt_pct_from_delta - 7.0 - 2.0
                    opt_return_open = max(opt_return_open, -90.0)

                    trades.append({
                        'Date': date_str,
                        'Ticker': ticker.replace('.NS', ''),
                        'Type': 'PE (Bearish)',
                        'Stock_Entry': round(stock_entry, 2),
                        'Stock_Exit_Open': round(stock_exit_open, 2),
                        'Stock_Gap_%': round(stock_gap_pct, 2),
                        'Option_Est_Return_%': round(opt_return_open, 2),
                        'Win': opt_return_open > 0
                    })

        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    trade_df = pd.DataFrame(trades)

    if trade_df.empty:
        print("No trades triggered. Consider loosening filter conditions.")
        return trade_df

    # Analytics
    total_trades = len(trade_df)
    ce_trades = trade_df[trade_df['Type'].str.contains('CE')]
    pe_trades = trade_df[trade_df['Type'].str.contains('PE')]

    win_trades = trade_df[trade_df['Win'] == True]
    loss_trades = trade_df[trade_df['Win'] == False]
    win_rate = (len(win_trades) / total_trades) * 100

    avg_stock_gap = trade_df['Stock_Gap_%'].mean()
    avg_opt_return = trade_df['Option_Est_Return_%'].mean()
    avg_win_opt = win_trades['Option_Est_Return_%'].mean() if not win_trades.empty else 0
    avg_loss_opt = loss_trades['Option_Est_Return_%'].mean() if not loss_trades.empty else 0

    gross_profit = win_trades['Option_Est_Return_%'].sum()
    gross_loss = abs(loss_trades['Option_Est_Return_%'].sum()) if not loss_trades.empty else 1e-9
    profit_factor = gross_profit / gross_loss

    print("==================== BACKTEST SUMMARY RESULTS ====================")
    print(f"Total Trades Generated       : {total_trades}")
    print(f"  - Bullish CE Trades        : {len(ce_trades)}")
    print(f"  - Bearish PE Trades        : {len(pe_trades)}")
    print(f"Win Rate (After Theta/Fees)  : {win_rate:.2f}%")
    print(f"Average Stock Gap            : {avg_stock_gap:+.2f}%")
    print(f"Average Option Return / Trade: {avg_opt_return:+.2f}%")
    print(f"Average Winning Trade (Opt)  : {avg_win_opt:+.2f}%")
    print(f"Average Losing Trade (Opt)   : {avg_loss_opt:+.2f}%")
    print(f"Profit Factor                : {profit_factor:.2f}")
    print("==================================================================\n")

    print("--- Performance Breakdown by Setup Type ---")
    for stype in ['CE (Bullish)', 'PE (Bearish)']:
        sub = trade_df[trade_df['Type'] == stype]
        if not sub.empty:
            sub_win = sub[sub['Win'] == True]
            print(f"[{stype}] Trades: {len(sub)}, Win Rate: {(len(sub_win)/len(sub))*100:.1f}%, Avg Opt Return: {sub['Option_Est_Return_%'].mean():+.2f}%")

    print("\n--- Recent 10 Trades Sample ---")
    print(trade_df.tail(10)[['Date', 'Ticker', 'Type', 'Stock_Gap_%', 'Option_Est_Return_%', 'Win']].to_string(index=False))

    trade_df.to_csv("btst_backtest_results.csv", index=False)
    print("\n[+] Full trade log saved to 'btst_backtest_results.csv'")
    return trade_df

if __name__ == "__main__":
    run_backtest(start_date="2023-01-01")
