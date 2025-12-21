from datetime import datetime, timedelta, time
from os import getenv
from pprint import pprint

import pandas as pd
import schwabdev
from alpha_vantage.fundamentaldata import FundamentalData
from dotenv import load_dotenv
import pytz

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


df = get_history_around_latest_earnings("GOOGL")

# earnings day at 3pm Eastern time
eastern = pytz.timezone("US/Eastern")
earnings_day = df['datetime'].dt.date.min()  # first day in dataset
print(earnings_day)

target_3pm = eastern.localize(datetime.combine(earnings_day, time(15,0)))

# The bar containing 3pm: datetime <= 3pm < datetime + 30min
three_pm_bar = df[
    (df['datetime'] <= target_3pm) &
    (df['datetime'] + pd.Timedelta(minutes=30) > target_3pm)
]

print(df)
print("---- 3pm candle ----")
print(three_pm_bar.iloc[0])
