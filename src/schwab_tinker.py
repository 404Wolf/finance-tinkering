from datetime import datetime, timedelta, timezone
from os import getenv
from time import sleep
from typing import Generator
from zoneinfo import ZoneInfo

import pandas as pd
from alpha_vantage.fundamentaldata import FundamentalData
from alpha_vantage.timeseries import TimeSeries
from dotenv import load_dotenv

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)

load_dotenv()

ALPHAVANTAGE_API_KEY = getenv("ALPHAVANTAGE_API_KEY")
SCHWAB_APP_KEY = getenv("SCHWAB_APP_KEY")
SCHWAB_APP_SECRET = getenv("SCHWAB_APP_SECRET")
if SCHWAB_APP_KEY is None or SCHWAB_APP_SECRET is None or ALPHAVANTAGE_API_KEY is None:
    raise ValueError(
        "SCHWAB_APP_KEY, SCHWAB_APP_SECRET, and ALPHAVANTAGE_API_KEY must be set"
    )

fd = FundamentalData(key=ALPHAVANTAGE_API_KEY)
ts = TimeSeries(key=ALPHAVANTAGE_API_KEY, output_format="pandas")

def get_date_range_intraday(start_date: datetime, end_date: datetime, ticker: str) -> pd.DataFrame:
    # Make start_date and end_date timezone aware
    end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    months = [
        datetime(year=start_date.year, month=i, day=1)
        for i in range(start_date.month, end_date.month + 1)
    ]

    data = pd.DataFrame()
    for month in months:
        month_str = month.strftime("%Y-%m")

        # print(f"symbol={ticker}, interval=60min, month={month_str}, outputsize=full")
        intraday_data: pd.DataFrame = ts.get_intraday(  # pyright: ignore[reportAssignmentType]
            symbol=ticker, interval="60min", month=month_str, outputsize="full"
        )[0]

        data = pd.concat([data, intraday_data])

    data = data.sort_index()

    # then filter with timezone-aware datetime objects
    data: pd.DataFrame = data[(data.index >= start_date) & (data.index <= end_date)]  # pyright: ignore[reportAssignmentType]

    return data

def get_history_around_previous_earnings(symbol: str, n: int = 1, j: int = 0) -> Generator[tuple[pd.DataFrame, datetime], None, None]:
    earnings: pd.DataFrame = pd.DataFrame(fd.get_earnings_quarterly(symbol)[0])

    for i in range(j, min(n, len(earnings))):
        earnings_row = earnings.iloc[i]
        earnings_date = datetime.strptime(earnings_row["reportedDate"], "%Y-%m-%d")

        # Use startDate/endDate to get data around earnings date
        # Get earnings date and two days after with 30-minute candles
        one_day_after = earnings_date + timedelta(days=1)

        intradata_data = get_date_range_intraday(earnings_date, one_day_after, symbol)

        yield (intradata_data, earnings_date)  # pyright: ignore[reportReturnType]


def get_3pm_to_next_day_post_earnings_spike_percent(ticker: str, history_around_earnings: pd.DataFrame) -> float:
    history_at_3pm = history_around_earnings[history_around_earnings.index.hour == 15]  # pyright: ignore[reportAttributeAccessIssue]

    # Get the datetime values for the two 3pm points
    earnings_date_3pm_time = history_at_3pm.index[0]
    next_day_3pm_time = history_at_3pm.index[1]

    # Filter data between the two 3pm times
    between_3pms = history_around_earnings[
        (history_around_earnings.index >= earnings_date_3pm_time)
        & (history_around_earnings.index <= next_day_3pm_time)
    ]
    # Open price at 3PM on day of earnings
    before_earnings_open = history_around_earnings[history_around_earnings.index == earnings_date_3pm_time].iloc[0]["1. open"]

    # Find the highest 'high' value between the two 3pms
    highest_after_before_earnings = between_3pms["2. high"].max()

    percent_increase = (highest_after_before_earnings / before_earnings_open) - 1

    return percent_increase

ticker = "TSLA"
for history_around_earnings, earnings_date in get_history_around_previous_earnings(ticker, n=5000, j=0):
    percent_increase = get_3pm_to_next_day_post_earnings_spike_percent(ticker, history_around_earnings)
    print(f"Percent Increase: {percent_increase:.2%} on {earnings_date}")
    print()
    sleep(.5)
