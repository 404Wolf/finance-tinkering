from datetime import datetime
from os import getenv

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


def get_date_range_intraday(start_date: datetime, end_date: datetime, ticker):
    end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    months = [
        datetime(year=start_date.year, month=i, day=1)
        for i in range(start_date.month, end_date.month + 1)
    ]

    data = pd.DataFrame()
    for month in months:
        month_str = month.strftime("%Y-%m")

        intraday_data: pd.DataFrame = ts.get_intraday(  # pyright: ignore[reportAssignmentType]
            symbol=ticker, interval="60min", month=month_str, outputsize="full"
        )[0]

        data = pd.concat([data, intraday_data])

    data = data.sort_index()
    data = data[(data.index >= start_date) & (data.index <= end_date)]

    return data


date_range_intraday = get_date_range_intraday(datetime(2022, 1, 31), datetime(2022, 2, 1), "AAPL")
