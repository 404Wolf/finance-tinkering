from datetime import datetime, time, timedelta
from os import getenv

from dotenv import load_dotenv
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpha_vantage.fundamentaldata import FundamentalData

load_dotenv()

# ------------------ clients ------------------

ALPHAVANTAGE_API_KEY = getenv("ALPHAVANTAGE_API_KEY")
SCHWAB_APP_KEY = getenv("SCHWAB_APP_KEY")
SCHWAB_APP_SECRET = getenv("SCHWAB_APP_SECRET")

ALPACA_SECRET_KEY = getenv("ALPACA_SECRET_KEY")
ALPACA_API_KEY = getenv("ALPACA_API_KEY")

client = StockHistoricalDataClient(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
)

fd = FundamentalData(key=ALPHAVANTAGE_API_KEY)

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)


# ------------------ earnings dates ------------------

def getEarningsDays(symbol: str, n: int = 3):
    earnings: pd.DataFrame = pd.DataFrame(
        fd.get_earnings_quarterly(symbol)[0]
    )

    results = []

    for i in range(min(n, len(earnings))):
        row = earnings.iloc[i]
        earnings_date = datetime.strptime(row["reportedDate"], "%Y-%m-%d")
        release_time = row["reportTime"]
        results.append([earnings_date, release_time])

    return results


# ------------------ core logic ------------------

def percent_move_3pm_to_next_3pm(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes percent move from first 3pm open
    to max high before next 3pm open.
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
        max_high = window["high"].max()

        percent_move = (max_high / open_3pm) - 1

        results.append({
            "start_3pm": start_ts,
            "open_3pm": open_3pm,
            "max_high": max_high,
            "percent_move": percent_move
        })

    return pd.DataFrame(results)


# ------------------ earnings spike wrapper ------------------

def get3pmspike(earningsDateData, symbol: str):
    all_results = []

    for earnings_date, release_time in earningsDateData:
        if release_time != "post-market":
            continue

        # fetch from earnings day through following day
        start = earnings_date
        end = earnings_date + timedelta(days=2)

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Hour,
            start=start,
            end=end,
        )
        bars = client.get_stock_bars(request)
        df = bars.df

        # normalize index
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

ticker = "NKE"
earnings = getEarningsDays(ticker, 3)
result = get3pmspike(earnings, ticker)

print(result)
