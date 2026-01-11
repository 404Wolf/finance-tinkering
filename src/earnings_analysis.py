import argparse
import re
from datetime import time

import numpy as np
import pandas as pd

from .utils.earnings import get_3pm_spike, get_earnings_days

parser = argparse.ArgumentParser(description='Analyze earnings data for a ticker')
parser.add_argument('ticker', type=str, help='Stock ticker symbol')
parser.add_argument('--fixed-threshold', '--ft', default=3, type=float, help='Fixed threshold for analysis')
parser.add_argument('--days-since', '--ds', default=16, type=int, help='Number of days since earnings announcement')
parser.add_argument('--reference-time', '--rt', default='3pm', type=str, help='Reference time for analysis (e.g., 3pm, 9am, 12:30pm)')
args = parser.parse_args()

ticker = args.ticker
fixed_threshold = args.fixed_threshold
days_since = args.days_since

def parse_time_string(time_str: str) -> time:
    """Parse time string like '3pm', '9am', '12:30pm' into datetime.time object."""
    time_str = time_str.lower().strip()
    
    # Match patterns like "3pm", "9am", "12:30pm"
    match = re.match(r'^(\d{1,2})(?::(\d{2}))?([ap]m)$', time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}. Use format like '3pm', '9am', or '12:30pm'")
    
    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    period = match.group(3)
    
    # Convert to 24-hour format
    if period == 'pm' and hour != 12:
        hour += 12
    elif period == 'am' and hour == 12:
        hour = 0
    
    return time(hour, minute)

reference_time = parse_time_string(args.reference_time)

def print_hypothetical(label: str, threshold: float, result: pd.DataFrame) -> None:
    hits = (result["percent_move_high"] > threshold).sum()
    total = len(result)
    conditional_value = np.where(
        result["percent_move_high"] > threshold,
        threshold,
        result["percent_move_open_to_open"]
    ).sum()

    mask = result["percent_move_high"] <= threshold
    open_moves_below = result.loc[mask, "percent_move_open_to_open"]

    avg_open_move_below = open_moves_below.mean()
    min_open_move_below = open_moves_below.min()

    conditional_value_normalized = conditional_value / total

    print(f"\n--- [{threshold:.3f}%] {label} Threshold ---")
    print(f"Hits: {hits}/{total}")
    print(f"Conditional result: {conditional_value:.3f}")
    print(f"Conditional result normalized: {conditional_value_normalized:.3f}%")
    print(f"Average Loss (threshold not met): {avg_open_move_below:.3f}%")
    print(f"Largest Loss (threshold not met): {min_open_move_below:.3f}%")

def find_optimal_threshold(result: pd.DataFrame, fixed_threshold: float) -> float:
    total_events = len(result)
    best_threshold = 0.0
    best_conditional_value_normalized = float("-inf")

    thresholds_to_try = np.arange(0, fixed_threshold + 0.001, 0.001)

    for threshold in thresholds_to_try:
        conditional_value = np.where(
            result["percent_move_high"] > threshold,
            threshold,
            result["percent_move_open_to_open"],
        ).sum()
        conditional_value_normalized = conditional_value / total_events

        if conditional_value_normalized > best_conditional_value_normalized:
            best_conditional_value_normalized = conditional_value_normalized
            best_threshold = threshold

    return best_threshold



if __name__ == '__main__':
    earnings = get_earnings_days(ticker, 20)
    earnings = earnings[:days_since]
    result = get_3pm_spike(earnings, ticker, reference_time)

    print(result)

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

    print()
    print(f"Summary statistics: {ticker}")

    print(f"Minimum Spike: {min_percent_move_high:.3f}%")
    print(f"Average Spike: {avg_percent_move_high:.3f}%")
    print(f"Median Spike: {median_percent_move_high:.3f}%")
    print(f"Earnings Count: {total_events}")

    for label, median_threshold in median_thresholds.items():
        print_hypothetical(label, median_threshold, result)

    print_hypothetical("Fixed", fixed_threshold, result)

    best_threshold = find_optimal_threshold(result, fixed_threshold)

    print_hypothetical("Optimal", best_threshold, result)

    print(f"\nAverage Loss No Threshold: {avg_negative_open_move:.2f}%")
    print(f"Largest Drop Overall: {lowest_open_move:.2f}%")
