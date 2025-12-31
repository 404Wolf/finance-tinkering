import os

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpha_vantage.fundamentaldata import FundamentalData
from dotenv import load_dotenv

__all__ = ["alpaca", "alpha_v"]

load_dotenv()

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

alpaca = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)

alpha_v = FundamentalData(key=ALPHAVANTAGE_API_KEY)

EARNINGS_DATA = pd.read_csv("data/earnings.csv")
