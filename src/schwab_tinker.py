from datetime import datetime, time, timedelta
from os import getenv
from pprint import pprint

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

def get_history_around_latest_earnings(symbol: str):
    earnings: pd.DataFrame = pd.DataFrame(fd.get_earnings_quarterly(symbol)[0])
    latest_earnings = earnings.iloc[0]

    earnings_date = datetime.strptime(latest_earnings["reportedDate"], "%Y-%m-%d")

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

    # Convert Schwab epoch (UTC) to US/Eastern
    df['datetime'] = (
        pd.to_datetime(df['datetime'], unit='ms')
        .dt.tz_localize('UTC')
        .dt.tz_convert('US/Eastern')
    )

    return df


df = get_history_around_latest_earnings("AAPL")
filtered_df = df[df['datetime'].dt.time == time(15, 0)]
earnings_date_3pm, next_day_3pm = filtered_df.iloc[0], filtered_df.iloc[1]

# Get the datetime values for the two 3pm points
earnings_date_3pm_time = earnings_date_3pm['datetime']
next_day_3pm_time = next_day_3pm['datetime']

# Filter data between the two 3pm times
between_3pms = df[(df['datetime'] >= earnings_date_3pm_time) & (df['datetime'] <= next_day_3pm_time)]

# Open price at 3PM on day of earnings
before_earnings_open = df[df['datetime'] == earnings_date_3pm_time].iloc[0]['open']

# Find the highest 'high' value between the two 3pms
highest_after_before_earnings = between_3pms['high'].max()

percent_increase = ((highest_after_before_earnings/before_earnings_open) - 1)

print(f"Percentage Increase: {percent_increase:.3%}")
