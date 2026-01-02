import numpy as np
import argparse

from .utils.earnings import get_3pm_spike, get_earnings_days

def earnings_analysis(ticker: str, fixed_threshold: float):
    earnings = get_earnings_days(ticker, 16)
    result = get_3pm_spike(earnings, ticker)
    print(result)

    if not result.empty:
        # Basic stats
        min_percent_move_high = result["percent_move_high"].min()
        avg_percent_move_high = result["percent_move_high"].mean()
        median_percent_move_high = result["percent_move_high"].median()

        count_above_fixed = (result["percent_move_high"] > fixed_threshold).sum()
        total_events = len(result)

        negative_open_moves = result.loc[
            result["percent_move_open_to_open"] < 0,
            "percent_move_open_to_open"
        ]

        avg_negative_open_move = (
            negative_open_moves.mean()
            if not negative_open_moves.empty
            else np.nan
        )

        lowest_open_move = result["percent_move_open_to_open"].min()

        # Fixed threshold conditional result
        conditional_fixed = np.where(
            result["percent_move_high"] > fixed_threshold,
            fixed_threshold,
            result["percent_move_open_to_open"]
        ).sum()

        mask_fixed = result["percent_move_high"] <= fixed_threshold
        open_moves_below_fixed = result.loc[mask_fixed, "percent_move_open_to_open"]

        avg_open_move_below_fixed = open_moves_below_fixed.mean()
        min_open_move_below_fixed = open_moves_below_fixed.min()

        median_minus_one_std = (
        result["percent_move_high"].median()
        - result["percent_move_high"].std()
        )

        # Median-based thresholds
        median_minus_one = median_percent_move_high - 1
        median_minus_one_std = (
            median_percent_move_high
            - result["percent_move_high"].std()
        )

        median_thresholds = {
            "Median - 1": median_minus_one,
            "Median - 1 Std Dev": median_minus_one_std,
        }

        print(f"\nSummary statistics: {ticker}")

        print(f"Minimum Spike: {min_percent_move_high:.2f}%")
        print(f"Average Spike: {avg_percent_move_high:.2f}%")
        print(f"Median Spike: {median_percent_move_high:.2f}%")
        print(f"Earnings Count: {total_events}")

        for label, median_threshold in median_thresholds.items():
            conditional_median = np.where(
                result["percent_move_high"] > median_threshold,
                median_threshold,
                result["percent_move_open_to_open"]
            ).sum()

            mask_median = result["percent_move_high"] <= median_threshold
            open_moves_below_median = result.loc[
                mask_median, "percent_move_open_to_open"
            ]

            avg_open_move_below_median = open_moves_below_median.mean()
            min_open_move_below_median = open_moves_below_median.min()

            print(f"\n--- {label} Threshold ({median_threshold:.2f}%) ---")
            print(f"Conditional result: {conditional_median:.2f}")
            print(f"Average Loss (threshold not met): {avg_open_move_below_median:.2f}%")
            print(f"Largest Loss (threshold not met): {min_open_move_below_median:.2f}%")

        print(f"\n--- Fixed Threshold ({fixed_threshold:.2f}%) ---")
        print(f"Number of Spikes > threshold: {count_above_fixed}")
        print(f"Conditional result: {conditional_fixed:.2f}")
        print(f"Average Loss (threshold not met): {avg_open_move_below_fixed:.2f}%")
        print(f"Largest Loss (threshold not met): {min_open_move_below_fixed:.2f}%")

        print(f"\nAverage Loss No Threshold: {avg_negative_open_move:.2f}%")
        print(f"Largest Drop Overall: {lowest_open_move:.2f}%")

    else:
        print("\nNo events to summarize.")

parser = argparse.ArgumentParser(description='Analyze earnings data for a ticker')
parser.add_argument('ticker', type=str, help='Stock ticker symbol')
parser.add_argument('fixed_threshold', type=float, help='Fixed threshold for analysis')
args = parser.parse_args()

ticker = args.ticker
fixed_threshold = args.fixed_threshold
earnings_analysis(ticker, fixed_threshold)
