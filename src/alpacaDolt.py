from datetime import datetime, time, timedelta
from pprint import pprint

import numpy as np
import pandas as pd
import pytz

from alpha_vantage.fundamentaldata import FundamentalData
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from dotenv import load_dotenv
load_dotenv()

import os

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
# ------------------ clients ------------------

client = StockHistoricalDataClient(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY
)

fd = FundamentalData(key=ALPHAVANTAGE_API_KEY)


pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)


# ------------------ earnings dates ------------------

def getEarningsDays(symbol: str, n: int = 3, csv_path: str = "earningsdata.csv"):
    earnings = pd.read_csv(csv_path)

    # filter for symbol
    earnings = earnings[earnings["act_symbol"] == symbol]

    # parse dates
    earnings["date"] = pd.to_datetime(earnings["date"])

    # exclude future earnings dates
    today = pd.Timestamp.now().normalize()
    earnings = earnings[earnings["date"] < today]

    # normalize release time labels
    earnings["release_time"] = earnings["when"].map({
        "After market close": "post-market",
        "Before market open": "pre-market"
    })

    # sort newest first
    earnings = earnings.sort_values("date", ascending=False)

    results = []

    for _, row in earnings.head(n).iterrows():
        earnings_date = row["date"].to_pydatetime()
        release_time = row["release_time"]
        results.append([earnings_date, release_time])

    #print(results)
    return results

# ------------------ core logic ------------------

def percent_move_3pm_to_next_3pm(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes:
      - percent move from first 3pm open to max high before next 3pm
      - open price of the next 3pm candle
      - percent move from first 3pm open to next 3pm open
    """

    df = df.sort_index(level="timestamp")

    timestamps = df.index.get_level_values("timestamp")
    is_3pm = timestamps.time == time(15, 0)

    three_pm_df = df[is_3pm]

    results = []

    for i in range(len(three_pm_df) - 1):
        start_idx = three_pm_df.index[i]
        end_idx = three_pm_df.index[i + 1]

        start_ts = start_idx[1]
        end_ts = end_idx[1]

        window = df.loc[
            (slice(None), slice(start_ts, end_ts)),
            :
        ]

        open_3pm = df.loc[start_idx, "open"]
        next_3pm_open = df.loc[end_idx, "open"]

        max_high = window["high"].max()

        percent_move_high = ((max_high / open_3pm) - 1)*100
        percent_move_open_to_open = ((next_3pm_open / open_3pm) - 1)*100

        results.append({
            "start_3pm": start_ts,
            "open_3pm": open_3pm,
            "next_3pm_open": next_3pm_open,
            "max_high": max_high,
            "percent_move_high": percent_move_high,
            "percent_move_open_to_open": percent_move_open_to_open,
        })

    return pd.DataFrame(results)


# ------------------ earnings spike wrapper ------------------

def get3pmspike(earningsDateData, symbol: str):
    all_results = []

    for earnings_date, release_time in earningsDateData:
        if release_time == "post-market":
            start = earnings_date
            end = earnings_date + timedelta(days=2)
        elif release_time == "pre-market":
            start = earnings_date - timedelta(days=1)
            end = earnings_date + timedelta(days=1)
        else: 
            print("Date error. Could be caused by before/after day being a weekend.")
            break

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Hour,
            start=start,
            end=end,
        )

        bars = client.get_stock_bars(request)
        df = bars.df

        df = df.reset_index()
        df["timestamp"] = df["timestamp"].dt.tz_convert("America/New_York")
        df = df.set_index(["symbol", "timestamp"])

        moves = percent_move_3pm_to_next_3pm(df)

        if not moves.empty:
            moves["earnings_date"] = earnings_date
            all_results.append(moves.iloc[0])

    if all_results:
        return pd.DataFrame(all_results)

    return pd.DataFrame()


# ------------------ run ------------------

ticker = "C"
earnings = getEarningsDays(ticker, 16)
result = get3pmspike(earnings, ticker)
print(result)



# ------------------ additional calculations ------------------

if not result.empty:
    fixed_threshold = 3  # 3 percent (already scaled)

    # ----- basic stats -----
    min_percent_move_high = result["percent_move_high"].min()
    avg_percent_move_high = result["percent_move_high"].mean()
    median_percent_move_high = result["percent_move_high"].median()

    count_above_fixed = (result["percent_move_high"] > fixed_threshold).sum()
    total_events = len(result)

    negative_open_moves = result.loc[
        result["percent_move_open_to_open"] < 0,
        "percent_move_open_to_open"
    ]

    avg_negative_open_move = (
        negative_open_moves.mean()
        if not negative_open_moves.empty
        else np.nan
    )

    lowest_open_move = result["percent_move_open_to_open"].min()

    # ----- fixed threshold conditional result -----
    conditional_fixed = np.where(
        result["percent_move_high"] > fixed_threshold,
        fixed_threshold,
        result["percent_move_open_to_open"]
    ).sum()

    mask_fixed = result["percent_move_high"] <= fixed_threshold
    open_moves_below_fixed = result.loc[mask_fixed, "percent_move_open_to_open"]

    avg_open_move_below_fixed = open_moves_below_fixed.mean()
    min_open_move_below_fixed = open_moves_below_fixed.min()

    median_minus_one_std = (
    result["percent_move_high"].median()
    - result["percent_move_high"].std()
    )
       # ----- median-based thresholds -----
    median_minus_one = median_percent_move_high - 1
    median_minus_one_std = (
        median_percent_move_high
        - result["percent_move_high"].std()
    )

    median_thresholds = {
        "Median - 1": median_minus_one,
        "Median - 1 Std Dev": median_minus_one_std,
    }
    
    print(f"\nSummary statistics: {ticker}")

    print(f"Minimum Spike: {min_percent_move_high:.2f}%")
    print(f"Average Spike: {avg_percent_move_high:.2f}%")
    print(f"Median Spike: {median_percent_move_high:.2f}%")
    print(f"Earnings Count: {total_events}")

    for label, median_threshold in median_thresholds.items():
        conditional_median = np.where(
            result["percent_move_high"] > median_threshold,
            median_threshold,
            result["percent_move_open_to_open"]
        ).sum()

        mask_median = result["percent_move_high"] <= median_threshold
        open_moves_below_median = result.loc[
            mask_median, "percent_move_open_to_open"
        ]

        avg_open_move_below_median = open_moves_below_median.mean()
        min_open_move_below_median = open_moves_below_median.min()

        print(f"\n--- {label} Threshold ({median_threshold:.2f}%) ---")
        print(f"Conditional result: {conditional_median:.2f}")
        print(f"Average Loss (threshold not met): {avg_open_move_below_median:.2f}%")
        print(f"Largest Loss (threshold not met): {min_open_move_below_median:.2f}%")


    # ----- output -----
    print(f"\nSummary statistics: {ticker}")

    print(f"Minimum Spike: {min_percent_move_high:.2f}%")
    print(f"Average Spike: {avg_percent_move_high:.2f}%")
    print(f"Median Spike: {median_percent_move_high:.2f}%")
    print(f"Earnings Count: {total_events}")

    print(f"\n--- Fixed Threshold ({fixed_threshold:.2f}%) ---")
    print(f"Number of Spikes > threshold: {count_above_fixed}")
    print(f"Conditional result: {conditional_fixed:.2f}")
    print(f"Average Loss (threshold not met): {avg_open_move_below_fixed:.2f}%")
    print(f"Largest Loss (threshold not met): {min_open_move_below_fixed:.2f}%")

    print(f"\n--- Median Threshold Minus 1 SD ({median_threshold:.2f}%) ---")
    print(f"Conditional result: {conditional_median:.2f}")
    print(f"Average Loss (threshold not met): {avg_open_move_below_median:.2f}%")
    print(f"Largest Loss (threshold not met): {min_open_move_below_median:.2f}%")

    print(f"\nAverage Loss No Threshold: {avg_negative_open_move:.2f}%")
    print(f"Largest Drop Overall: {lowest_open_move:.2f}%")


else:
    print("\nNo events to summarize.")