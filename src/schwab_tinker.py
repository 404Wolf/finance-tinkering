from datetime import datetime, time, timedelta
from os import getenv
from pprint import pprint
import yfinance as yf

import numpy as np
import pandas as pd
import pytz
import schwabdev
from alpha_vantage.fundamentaldata import FundamentalData
from dotenv import load_dotenv

pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)

load_dotenv()

ALPHAVANTAGE_API_KEY = getenv("ALPHAVANTAGE_API_KEY")
SCHWAB_APP_KEY = getenv("SCHWAB_APP_KEY")
SCHWAB_APP_SECRET = getenv("SCHWAB_APP_SECRET")
if SCHWAB_APP_KEY is None or SCHWAB_APP_SECRET is None or ALPHAVANTAGE_API_KEY is None:
    raise ValueError("SCHWAB_APP_KEY, SCHWAB_APP_SECRET, and ALPHAVANTAGE_API_KEY must be set")

client = schwabdev.Client(SCHWAB_APP_KEY, SCHWAB_APP_SECRET, tokens_db=".tokens")

fd = FundamentalData(key=ALPHAVANTAGE_API_KEY)

def get_history_around_latest_earnings(symbol: str, n: int = 1):
    earnings: pd.DataFrame = pd.DataFrame(fd.get_earnings_quarterly(symbol)[0])

    results = []

    for i in range(min(n, len(earnings))):
        earnings_row = earnings.iloc[i]
        earnings_date = datetime.strptime(earnings_row["reportedDate"], "%Y-%m-%d")

        # Use startDate/endDate to get data around earnings date
        # Get earnings date and two days after with 30-minute candles
        two_days_after = earnings_date + timedelta(days=2)

        history = client.price_history(
            symbol,
            startDate=earnings_date,
            endDate=two_days_after,
            frequencyType="minute",
            frequency=30,
            needExtendedHoursData=True
        )

        candles = history.json()['candles']
        df = pd.DataFrame(candles)
        if df.empty:
            print("No data available for this earnings date.")
            exit()

        # Convert Schwab epoch (UTC) to US/Eastern
        df['datetime'] = (
            pd.to_datetime(df['datetime'], unit='ms')
            .dt.tz_localize('UTC')
            .dt.tz_convert('US/Eastern')
        )

        results.append(df)

    return results


def get_3pm_to_next_day_post_earnings_spike_percent(ticker, data) -> float:
    filtered_df = data[data['datetime'].dt.time == time(15, 0)]
    earnings_date_3pm, next_day_3pm = filtered_df.iloc[0], filtered_df.iloc[1]

    # Get the datetime values for the two 3pm points
    earnings_date_3pm_time = earnings_date_3pm['datetime']
    next_day_3pm_time = next_day_3pm['datetime']

    # Filter data between the two 3pm times
    between_3pms = data[(data['datetime'] >= earnings_date_3pm_time) & (data['datetime'] <= next_day_3pm_time)]

    # Open price at 3PM on day of earnings
    before_earnings_open = data[data['datetime'] == earnings_date_3pm_time].iloc[0]['open']

    # Find the highest 'high' value between the two 3pms
    highest_after_before_earnings = between_3pms['high'].max()

    percent_increase = ((highest_after_before_earnings/before_earnings_open) - 1)

    return percent_increase

ticker = 'NKE'
history_around_earnings_appl = get_history_around_latest_earnings(ticker, n=3)
for df in history_around_earnings_appl:
    percent_increase = get_3pm_to_next_day_post_earnings_spike_percent(ticker, df)
    print(f"Percent Increase: {percent_increase:.2%}")
    print()
