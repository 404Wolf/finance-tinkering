from datetime import datetime, time, timedelta
from os import getenv

import numpy as np
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpha_vantage.fundamentaldata import FundamentalData
from dotenv import load_dotenv

load_dotenv()

ALPHAVANTAGE_API_KEY = getenv("ALPHAVANTAGE_API_KEY")
SCHWAB_APP_KEY = getenv("SCHWAB_APP_KEY")
SCHWAB_APP_SECRET = getenv("SCHWAB_APP_SECRET")

ALPACA_SECRET_KEY = getenv("ALPACA_SECRET_KEY")
ALPACA_API_KEY = getenv("ALPACA_API_KEY")

alpaca = StockHistoricalDataClient(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
)

fd = FundamentalData(key=ALPHAVANTAGE_API_KEY)

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)


def getEarningsDays(symbol: str, n: int = 3) -> list[tuple[datetime, str]]:
    earnings: pd.DataFrame = pd.DataFrame(fd.get_earnings_quarterly(symbol)[0])

    results: list[tuple[datetime, str]] = []

    for i in range(min(n, len(earnings))):
        row = earnings.iloc[i]
        earnings_date = datetime.strptime(row["reportedDate"], "%Y-%m-%d")
        release_time: str = row["reportTime"]
        results.append((earnings_date, release_time))

    return results


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

        bars = alpaca.get_stock_bars(request)
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


def summarize_result(ticker: str, n_earnings: int = 16, threshold: float = 3):
    earnings = getEarningsDays(ticker, n_earnings)
    result = get3pmspike(earnings, ticker)

    if not result.empty:
        min_percent_move_high = result["percent_move_high"].min()

        count_above_3pct = (result["percent_move_high"] > threshold).sum()

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

        avg_percent_move_high = result["percent_move_high"].mean()

        conditional_result = np.where(
            result["percent_move_high"] > threshold,
            threshold,
            result["percent_move_open_to_open"]
        ).sum()

        mask = result["percent_move_high"] <= threshold
        open_moves_below_threshold = result.loc[mask, "percent_move_open_to_open"]

        avg_open_move_below_threshold = open_moves_below_threshold.mean()
        min_open_move_below_threshold = open_moves_below_threshold.min()

        print("\nSummary statistics:")
        print(f"Minimum Spike: {min_percent_move_high:.4f}")
        print(f"Average Spike: {avg_percent_move_high:.4f}")
        print(f"Number of Spikes > {threshold}%: {count_above_3pct}")
        print(f"Earnings Count: {total_events}")
        print(f"Average Loss No Threshold: {avg_negative_open_move:.4f}")
        print(f"Largest Drop: {lowest_open_move:.4f}")
        print(f"Conditional result (threshold={threshold:.2f}): {conditional_result:.4f}")
        print(f"Average Loss (threshold not met): {avg_open_move_below_threshold:.4f}")
        print(f"Largest Loss (threshold not met): {min_open_move_below_threshold:.4f}")

    else:
        print("\nNo events to summarize.")


summarize_result("CCL", 16)
