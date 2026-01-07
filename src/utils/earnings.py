import datetime
from datetime import time, timedelta
from typing import Literal

import pandas as pd
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from . import memory
from .clients import EARNINGS_DATA, alpaca


ReleaseTime = Literal["post-market", "pre-market"]
EarningsDaysData = list[tuple[datetime.datetime, ReleaseTime]]

def get_earnings_days( ticker: str, days_since: int = 3) -> EarningsDaysData:
    """
    Get the next n earnings days for a given ticker.
    """

    # filter for symbol
    earnings = EARNINGS_DATA[EARNINGS_DATA["act_symbol"] == ticker]

    # parse dates
    earnings = earnings.copy()
    earnings["date"] = pd.to_datetime(earnings["date"])

    # exclude future earnings dates
    today = pd.Timestamp.now().normalize()
    earnings = earnings[earnings["date"] < today]

    # normalize release time labels
    earnings["release_time"] = earnings["when"].map({  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]
        "After market close": "post-market",
        "Before market open": "pre-market"
    })

    # Sort newest first
    earnings = earnings.sort_values("date", ascending=False)  # pyright: ignore[reportCallIssue, reportAttributeAccessIssue]

    results: EarningsDaysData = []

    for _, row in earnings.head(days_since).iterrows():
        earnings_date: datetime.datetime = row["date"].to_pydatetime().date()  # pyright: ignore[reportAttributeAccessIssue]
        release_time: Literal["post-market", "pre-market"] = row["release_time"]  # pyright: ignore[reportAssignmentType]
        results.append((earnings_date, release_time))

    return results

def percent_move_3pm_to_next_3pm(df: pd.DataFrame, reference_time: time = time(15, 0)) -> pd.DataFrame:
    """
    Computes:
      - percent move from first reference time open to max high before next reference time
      - open price of the next reference time candle
      - percent move from first reference time open to next reference time open
    
    Args:
        df: DataFrame with timestamp index
        reference_time: Time to use as reference point (default: 3pm)
    """

    df = df.sort_index(level="timestamp")

    timestamps = df.index.get_level_values("timestamp")
    is_reference_time = timestamps.time == reference_time  # pyright: ignore[reportAttributeAccessIssue]

    three_pm_df: pd.DataFrame = df[is_reference_time]  # pyright: ignore[reportAssignmentType]

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

        open_reference = df.loc[start_idx, "open"]
        next_reference_open = df.loc[end_idx, "open"]

        max_high = window["high"].max()

        percent_move_high = ((max_high / open_reference) - 1)*100
        percent_move_open_to_open = ((next_reference_open / open_reference) - 1)*100

        results.append({
            "start_3pm": start_ts,
            "open_3pm": open_reference,
            "next_3pm_open": next_reference_open,
            "max_high": max_high,
            "percent_move_high": percent_move_high,
            "percent_move_open_to_open": percent_move_open_to_open,
        })

    return pd.DataFrame(results)

@memory.cache
def get_3pm_spike(earnings_date_data: EarningsDaysData, symbol: str, reference_time: time = time(15, 0)):
    """
    Get spike data for earnings events using a configurable reference time.
    
    Args:
        earnings_date_data: List of earnings dates and release times
        symbol: Stock ticker symbol
        reference_time: Time to use as reference point (default: 3pm)
    """
    all_results = []

    for earnings_date, release_time in earnings_date_data:
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
            timeframe=TimeFrame.Hour,  # pyright: ignore[reportArgumentType]
            start=start,
            end=end,
        )

        bars = alpaca.get_stock_bars(request)

        df = bars.df  # pyright: ignore[reportAttributeAccessIssue]

        df = df.reset_index()
        df["timestamp"] = df["timestamp"].dt.tz_convert("America/New_York")
        df = df.set_index(["symbol", "timestamp"])

        moves = percent_move_3pm_to_next_3pm(df, reference_time)

        if not moves.empty:
            moves["earnings_date"] = earnings_date
            all_results.append(moves.iloc[0])

    if all_results:
        return pd.DataFrame(all_results)
    else:
        raise ValueError("No data found")


def get_earnings_window_data(earnings_date: datetime.datetime, symbol: str) -> pd.DataFrame:
    """
    Fetch OHLC data from day before earnings (for 3pm reference) through day after.
    Returns DataFrame with timestamp index and OHLC columns.
    """
    start = earnings_date - timedelta(days=1)
    end = earnings_date + timedelta(days=2)

    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Hour,  # pyright: ignore[reportArgumentType]
        start=start,
        end=end,
    )

    bars = alpaca.get_stock_bars(request)
    df = bars.df  # pyright: ignore[reportAttributeAccessIssue]

    df = df.reset_index()
    df["timestamp"] = df["timestamp"].dt.tz_convert("America/New_York")
    df = df.set_index("timestamp")
    df = df.drop(columns=["symbol"])

    # Rename columns to match mplfinance requirements
    df.columns = ["Open", "High", "Low", "Close", "Volume", "trade_count", "vwap"]

    return df[["Open", "High", "Low", "Close", "Volume"]]  # pyright: ignore[reportReturnType]
