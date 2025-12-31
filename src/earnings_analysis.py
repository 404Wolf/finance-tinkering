"""
Simple earnings data analysis - no ML, just print the data.
"""

import numpy as np
import pandas as pd
from datetime import timedelta, time
import pytz

from .utils.earnings import get_earnings_days, get_earnings_window_data
from .utils.clients import alpaca
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


def analyze_earnings(ticker: str, n_quarters: int = 20):
    """
    For each earnings event, print:
    - Date
    - Leading momentum
    - Leading IV (volatility)
    - Max spike %
    - Min dip %
    """
    print(f"\n{'='*80}")
    print(f"Earnings Analysis: {ticker}")
    print(f"{'='*80}\n")

    eastern = pytz.timezone("America/New_York")
    earnings_data = get_earnings_days(ticker, n_quarters)

    results = []

    for earnings_date, release_time in earnings_data:
        try:
            # Get historical data for momentum/volatility
            start = earnings_date - timedelta(days=30)
            end = earnings_date

            request = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
            )

            bars = alpaca.get_stock_bars(request)
            df_hist = bars.df
            df_hist = df_hist.reset_index()
            df_hist = df_hist.sort_values("timestamp")

            if len(df_hist) < 10:
                continue

            # Calculate momentum and volatility
            returns = df_hist["close"].pct_change().dropna()

            momentum_5d = (df_hist["close"].iloc[-1] / df_hist["close"].iloc[-6] - 1) * 100 if len(df_hist) >= 6 else 0
            volatility_20d = returns.tail(20).std() * np.sqrt(252) * 100

            # Get earnings window data
            df_earnings = get_earnings_window_data(earnings_date, ticker)
            if df_earnings.empty:
                continue

            # Reference: 3pm day before
            day_before = earnings_date - timedelta(days=1)
            three_pm_before = eastern.localize(pd.Timestamp.combine(day_before, time(15, 0)))

            time_diffs = abs(df_earnings.index - three_pm_before)
            reference_price = df_earnings.iloc[time_diffs.argmin()]["Open"]

            # Calculate % from reference
            df_pct = df_earnings.copy()
            for col in ["Open", "High", "Low", "Close"]:
                df_pct[col] = ((df_earnings[col] / reference_price) - 1) * 100

            # Window: 3pm before to 3pm after
            three_pm_after = eastern.localize(pd.Timestamp.combine(earnings_date + timedelta(days=1), time(15, 0)))
            df_window = df_pct[(df_pct.index >= three_pm_before) & (df_pct.index <= three_pm_after)]

            if df_window.empty:
                continue

            # Max and min
            max_spike = df_window["High"].max()
            min_dip = df_window["Low"].min()

            results.append({
                'date': earnings_date,
                'timing': release_time,
                'momentum_5d': momentum_5d,
                'iv_20d': volatility_20d,
                'max_spike': max_spike,
                'min_dip': min_dip
            })

        except Exception as e:
            print(f"Error on {earnings_date}: {e}")
            continue

    # Print results
    print(f"{'Date':<12} {'Timing':<12} {'Mom 5d':>8} {'IV 20d':>8} {'Max %':>8} {'Min %':>8}")
    print("-" * 80)

    for r in results:
        print(f"{str(r['date']):<12} {r['timing']:<12} {r['momentum_5d']:>7.2f}% {r['iv_20d']:>7.2f}% {r['max_spike']:>7.2f}% {r['min_dip']:>7.2f}%")


if __name__ == "__main__":
    tickers = ["AAPL", "TSLA", "NVDA", "MSFT"]

    for ticker in tickers:
        analyze_earnings(ticker, n_quarters=20)
        print("\n")
