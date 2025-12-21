import datetime as dt

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf


def fetch_spx_history():
    start = "1950-01-01"
    end = dt.date.today().isoformat()

    df = yf.download("^GSPC", start=start, end=end, progress=False)
    if df is None or df.empty:
        raise RuntimeError("Failed to fetch data for ^GSPC. Check yfinance / network.")

    df = df[["Close"]].rename(columns={"Close": "SPX"})
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    return df


def generate_xxx_history(spx_df, start_value=100_000.0, start_date="1973-01-11", end_date=None, leverage=3.0, annual_fee_pct=1.0, tracking_error_std=0.001):
    """
    Simulate leveraged ETF performance with realistic tracking errors and fees.

    Parameters:
    - spx_df: DataFrame with S&P 500 data (must have 'SPX' column)
    - start_value: Initial investment amount
    - start_date: When to start the simulation
    - end_date: When to end the simulation (None = to end of data)
    - leverage: Leverage factor (e.g., 3.0 for 3x leverage)
    - annual_fee_pct: Annual expense ratio in percent
    - tracking_error_std: Standard deviation of daily tracking error

    Returns:
    - DataFrame with both S&P 500 and leveraged ETF performance
    """
    df = spx_df.copy()

    # Convert start date to datetime
    start_date = pd.to_datetime(start_date)

    # Find next trading day if start date isn't a trading day
    if start_date not in df.index:
        start_date = df.index[df.index.searchsorted(start_date)]

    # Filter data from start date onward
    if end_date is not None:
        end_date = pd.to_datetime(end_date)
        df = df.loc[start_date:end_date].copy()
    else:
        df = df.loc[start_date:].copy()

    # Calculate S&P returns
    df["SPX_ret"] = df["SPX"].pct_change()
    df = df.iloc[1:].copy()  # Remove first row (NaN return)

    # Calculate S&P value over time
    df["SPX_value"] = start_value * (1.0 + df["SPX_ret"]).cumprod()

    # Calculate daily fee rate (compounded daily)
    daily_fee_rate = (1 + annual_fee_pct/100) ** (1/252) - 1

    # Calculate leveraged returns with tracking error and fees
    # 1. Apply leverage
    xxx_ret = leverage * df["SPX_ret"]

    # 2. Add random tracking error (normally distributed)
    np.random.seed(42)  # For reproducibility
    tracking_errors = np.random.normal(0, tracking_error_std, len(df))
    xxx_ret = xxx_ret + tracking_errors

    # 3. Apply daily fee
    xxx_ret = xxx_ret - daily_fee_rate

    # 4. Prevent bankruptcy (limit losses to 100%)
    xxx_ret = np.maximum(xxx_ret, -1.0)

    df["XXX_ret"] = xxx_ret
    df["XXX_value"] = start_value * (1.0 + df["XXX_ret"]).cumprod()

    # Rename columns for clarity
    df.rename(columns={"SPX": "SPX_price"}, inplace=True)

    # Add columns to track impact of fees and tracking error
    df["XXX_perfect"] = start_value * (1.0 + np.maximum(leverage * df["SPX_ret"], -1.0)).cumprod()
    df["Fee_impact"] = df["XXX_perfect"] - df["XXX_value"]

    return df


def main():
    start_capital = 100_000.0
    first_start_date = "1973-01-01"
    last_date = "2023-05-31"
    holding_period_years = 20

    print("Fetching S&P 500 (^GSPC) history...")
    spx_df = fetch_spx_history()

    # Filter to start from 1973 and end at 2019
    first_start_date = pd.to_datetime(first_start_date)
    last_date = pd.to_datetime(last_date)
    spx_df = spx_df.loc[first_start_date:last_date].copy()

    print(f"Testing all {holding_period_years}-year windows from {spx_df.index[0].date()} to {spx_df.index[-1].date()}...")

    results = []

    # Try starting on each trading day
    for i, start_date in enumerate(spx_df.index):
        if i % 500 == 0:
            print(f"Progress: {i}/{len(spx_df.index)} dates tested...")

        # Calculate end date (15 years later)
        end_date = start_date + pd.DateOffset(years=holding_period_years)

        # Check if we have enough data for the full window
        if end_date > spx_df.index[-1]:
            continue

        try:
            paths = generate_xxx_history(spx_df, start_value=start_capital, start_date=start_date, end_date=end_date, leverage=3.0)

            # Get final values
            final_spx = paths["SPX_value"].iloc[-1]
            final_xxx = paths["XXX_value"].iloc[-1]

            # Check if leveraged ETF came out ahead
            xxx_ahead = final_xxx > final_spx

            results.append({
                'start_date': start_date,
                'end_date': paths.index[-1],
                'final_spx': final_spx,
                'final_xxx': final_xxx,
                'xxx_ahead': xxx_ahead,
                'days_held': len(paths)
            })
        except Exception as e:
            print(f"Error on {start_date}: {e}")
            continue

    results_df = pd.DataFrame(results)

    # Calculate statistics
    total_tests = len(results_df)
    xxx_wins = results_df['xxx_ahead'].sum()
    win_rate = (xxx_wins / total_tests) * 100

    print("\n" + "="*60)
    print(f"RESULTS - {holding_period_years} YEAR HOLDING PERIODS")
    print("="*60)
    print(f"Total {holding_period_years}-year windows tested: {total_tests}")
    print(f"Times 3x ETF came out ahead: {xxx_wins}")
    print(f"Times S&P 500 came out ahead: {total_tests - xxx_wins}")
    print(f"Win rate for 3x ETF: {win_rate:.2f}%")
    print("="*60)

    # Show some example results
    print("\nFirst 10 start dates:")
    print(results_df.head(10)[['start_date', 'end_date', 'final_spx', 'final_xxx', 'xxx_ahead']])

    print("\nLast 10 start dates:")
    print(results_df.tail(10)[['start_date', 'end_date', 'final_spx', 'final_xxx', 'xxx_ahead']])

    # Plot win rate over time
    plt.figure(figsize=(12, 6))
    results_df['win_rate_rolling'] = results_df['xxx_ahead'].rolling(window=252, min_periods=1).mean() * 100
    plt.plot(results_df['start_date'], results_df['win_rate_rolling'], linewidth=2)
    plt.axhline(y=50, color='r', linestyle='--', alpha=0.5, label='50% (breakeven)')
    plt.xlabel("Start Date")
    plt.ylabel("Win Rate (%) - 252 day rolling window")
    plt.title(f"3x Leveraged ETF Win Rate vs S&P 500 ({holding_period_years}-Year Windows)\n(Overall: {win_rate:.2f}%)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
