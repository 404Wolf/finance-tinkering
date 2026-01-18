import pandas as pd
import requests
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
import os

# Load .env from the same directory as this script
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

ALPACA_KEY = os.environ["ALPACA_API_KEY"]
ALPACA_SECRET = os.environ["ALPACA_SECRET_KEY"]

CSV_PATH = Path("data/tradingdays.csv")

BASE_URL = "https://api.alpaca.markets/v2/calendar"

HEADERS = {
    "APCA-API-KEY-ID": ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
}

# 1. Load existing CSV
df = pd.read_csv(CSV_PATH, parse_dates=["date"])

last_date = df["date"].max().date()

# 2. Define fetch window
start = last_date + timedelta(days=1)
end = date.today().replace(year=date.today().year + 1)

# 3. Fetch calendar from Alpaca
resp = requests.get(
    BASE_URL,
    headers=HEADERS,
    params={
        "start": start.isoformat(),
        "end": end.isoformat(),
    },
    timeout=30,
)
resp.raise_for_status()

calendar = resp.json()

if not calendar:
    print("No new trading days to add.")
    raise SystemExit(0)

# 4. Normalize response
new_df = pd.DataFrame(calendar)
new_df["date"] = pd.to_datetime(new_df["date"])

cols = ["date", "open", "close", "session_open", "session_close"]
new_df = new_df[cols]

# 5. Append + de-duplicate
updated = (
    pd.concat([df, new_df], ignore_index=True)
      .drop_duplicates(subset=["date"])
      .sort_values("date")
)

# 6. Write back
updated.to_csv(CSV_PATH, index=False)

print(f"Added {len(updated) - len(df)} new trading days.")
