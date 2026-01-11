import pandas as pd

CALENDAR_PATH = "data/tradingdays.csv"

_calendar_df = pd.read_csv(
    CALENDAR_PATH,
    parse_dates=["date"],
)

_calendar_df["date"] = (
    _calendar_df["date"]
    .dt.tz_localize("America/New_York")
)

_calendar_df = _calendar_df.sort_values("date").reset_index(drop=True)

trading_days = _calendar_df["date"].to_numpy()