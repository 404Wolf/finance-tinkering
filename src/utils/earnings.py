import datetime
from datetime import date, time, timedelta
from typing import Literal
import os
import glob

import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from .clients import EARNINGS_DATA, alpaca
from .trading_calendar import trading_days
from . import memory


def prev_trading_day(date):
    idx = trading_days.searchsorted(date)
    if idx == 0:
        raise ValueError("No previous trading day")
    return trading_days[idx - 1]

def next_trading_day(date):
    idx = trading_days.searchsorted(date, side="right")
    if idx == len(trading_days):
        raise ValueError("No next trading day")
    return trading_days[idx]

def get_earnings_days( ticker: str, n: int = 3) -> list[tuple[date, Literal["post-market", "pre-market"]]]:
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

    results: list[tuple[datetime.date, Literal["post-market", "pre-market"]]] = []
    
    for _, row in earnings.head(n).iterrows():
        earnings_date: datetime.date = row["date"].to_pydatetime().date()  # pyright: ignore[reportAttributeAccessIssue]
        release_time: Literal["post-market", "pre-market"] = row["release_time"]  # pyright: ignore[reportAssignmentType]
        results.append((earnings_date, release_time))

    return results

def percent_move_3pm_to_next_3pm(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes:
      - percent move from first 3pm open to max high before next 3pm
      - open price of the next 3pm candle
      - percent move from first 3pm open to next 3pm open
    """

    df = df.sort_index(level="timestamp")

    timestamps = df.index.get_level_values("timestamp")
    is_3pm = timestamps.time == time(15, 0)  # pyright: ignore[reportAttributeAccessIssue]

    three_pm_df: pd.DataFrame = df[is_3pm]  # pyright: ignore[reportAssignmentType]

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
        next_3pm_open = df.loc[end_idx, "open"]

        max_high = window["high"].max()

        percent_move_high = ((max_high / open_3pm) - 1)*100
        percent_move_open_to_open = ((next_3pm_open / open_3pm) - 1)*100

        results.append({
            "start_3pm": start_ts,
            "open_3pm": open_3pm,
            "next_3pm_open": next_3pm_open,
            "max_high": max_high,
            "percent_move_high": percent_move_high,
            "percent_move_open_to_open": percent_move_open_to_open,
        })

    return pd.DataFrame(results)

@memory.cache
def get_3pm_spike(earnings_date_data: pd.DataFrame, symbol: str):
    all_results = []

    for earnings_date, release_time in earnings_date_data:
        earnings_date = pd.Timestamp(earnings_date).tz_localize("America/New_York")

        if release_time == "post-market":
            start = earnings_date
            end = next_trading_day(next_trading_day(earnings_date))
        elif release_time == "pre-market":
            start = prev_trading_day(earnings_date)
            end = next_trading_day(earnings_date)
        else:
            raise ValueError("Earnings release time missing")
            print("Earnings release time missing from spreadsheet")
            

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
        moves = percent_move_3pm_to_next_3pm(df)

        if not moves.empty:
            moves["earnings_date"] = earnings_date
            all_results.append(moves.iloc[0])

    if all_results:
        return pd.DataFrame(all_results)
    else:
        raise ValueError("No data found")


def get_earnings_window_data(earnings_date: date, symbol: str) -> pd.DataFrame:
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

    return df[["Open", "High", "Low", "Close", "Volume"]]

def plot_earnings_candles(
    earnings_date: date,
    release_time: Literal["post-market", "pre-market"],
    symbol: str,
    output_dir: str = "./plots"
):
    """
    Create a candlestick plot showing % change from 3pm the day before earnings.
    """
    import pytz

    df = get_earnings_window_data(earnings_date, symbol)
    if df.empty:
        print(f"No data for {earnings_date}")
        return

    # Find 3pm bar on day before earnings
    eastern = pytz.timezone("America/New_York")
    day_before = earnings_date - timedelta(days=1)
    three_pm_before = eastern.localize(datetime.datetime.combine(day_before, time(15, 0)))

    # Get reference price (3pm open price)
    time_diffs = abs(df.index - three_pm_before)
    reference_price = df.iloc[time_diffs.argmin()]["Open"]

    # Convert prices to % change (keep volume unchanged)
    df_pct = df.copy()
    for col in ["Open", "High", "Low", "Close"]:
        df_pct[col] = ((df[col] / reference_price) - 1) * 100

    # Filter to only show data from 3pm reference point onwards
    df_pct = df_pct[df_pct.index >= three_pm_before]

    # Earnings timestamp
    earnings_hour = time(16, 0) if release_time == "post-market" else time(9, 30)
    earnings_time = eastern.localize(datetime.datetime.combine(earnings_date, earnings_hour))

    # 3pm after earnings
    three_pm_after = eastern.localize(datetime.datetime.combine(earnings_date + timedelta(days=1), time(15, 0)))

    # Save plot
    year = earnings_date.year
    quarter = (earnings_date.month - 1) // 3 + 1
    filepath = os.path.join(output_dir, f"q{quarter}-{year}.png")
    os.makedirs(output_dir, exist_ok=True)

    mpf.plot(
        df_pct,
        type="candle",
        style="charles",
        title=f"{symbol} Q{quarter}-{year} ({release_time})",
        ylabel="% Change from 3pm Day Before",
        volume=False,
        vlines=dict(vlines=[three_pm_before, earnings_time, three_pm_after], colors=["blue", "red", "blue"], linewidths=2, alpha=0.7),
        savefig=filepath,
    )

    print(f"Saved plot: {filepath}")


def create_earnings_grid(symbol: str, plots_dir: str = "./plots", output_path: str = "./plots/earnings_grid.png"):
    """
    Create a grid of all earnings plots.
    """
    # Get all plot files
    plot_files = sorted(glob.glob(os.path.join(plots_dir, "q*.png")))

    if not plot_files:
        print("No plots found to create grid")
        return

    n_plots = len(plot_files)

    # Calculate grid dimensions (try to make it roughly square)
    n_cols = int(n_plots ** 0.5) + (1 if n_plots ** 0.5 % 1 > 0 else 0)
    n_rows = (n_plots + n_cols - 1) // n_cols

    # Create figure with subplots
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 4 * n_rows))

    # Flatten axes array for easier iteration
    if n_rows == 1 and n_cols == 1:
        axes = [axes]
    else:
        axes = axes.flatten() if n_rows > 1 or n_cols > 1 else [axes]

    # Plot each image
    for idx, plot_file in enumerate(plot_files):
        img = mpimg.imread(plot_file)
        axes[idx].imshow(img)
        axes[idx].axis('off')

        # Extract quarter info from filename for title
        filename = os.path.basename(plot_file)
        axes[idx].set_title(filename.replace('.png', '').upper(), fontsize=10, pad=5)

    # Hide unused subplots
    for idx in range(n_plots, len(axes)):
        axes[idx].axis('off')

    plt.suptitle(f"{symbol} Earnings Analysis - All Quarters", fontsize=16, y=0.995)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"Saved earnings grid: {output_path}")
