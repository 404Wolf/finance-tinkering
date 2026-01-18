import argparse

import numpy as np
import pandas as pd
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from html import escape
from .utils.earnings import get_3pm_spike, get_earnings_days

parser = argparse.ArgumentParser(description='Analyze earnings data for a ticker')
parser.add_argument('ticker', type=str, help='Stock ticker symbol')
parser.add_argument('--fixed-threshold', '--ft', default=3, type=float, help='Fixed threshold for analysis')
args = parser.parse_args()

ticker = args.ticker
fixed_threshold = args.fixed_threshold

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

import sys

class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()

def write_html(ticker: str, text: str) -> None:
    path = OUTPUT_DIR / f"{ticker}.html"
    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>{ticker}</title>
  <style>
    body {{
      font-family: monospace;
      background: #111;
      color: #eee;
      padding: 1rem;
    }}
    pre {{
      white-space: pre-wrap;
    }}
  </style>
</head>
<body>
<h1>{ticker}</h1>
<pre>{escape(text)}</pre>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")

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

    print(f"\n--- [{threshold:.2f}%] {label} Threshold ---")
    print(f"Hits: {hits}/{total}")
    print(f"Conditional result: {conditional_value:.2f}")
    print(f"Average Loss (threshold not met): {avg_open_move_below:.2f}%")
    print(f"Largest Loss (threshold not met): {min_open_move_below:.2f}%")

def run_analysis(ticker: str, fixed_threshold: float) -> None:
    earnings = get_earnings_days(ticker, 16)
    result = get_3pm_spike(earnings, ticker)
    print(result)

    if not result.empty:
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

        print(f"Minimum Spike: {min_percent_move_high:.2f}%")
        print(f"Average Spike: {avg_percent_move_high:.2f}%")
        print(f"Median Spike: {median_percent_move_high:.2f}%")
        print(f"Earnings Count: {total_events}")

        for label, median_threshold in median_thresholds.items():
            print_hypothetical(label, median_threshold, result)

        print_hypothetical("Fixed", fixed_threshold, result)

        print(f"\nAverage Loss No Threshold: {avg_negative_open_move:.2f}%")
        print(f"Largest Drop Overall: {lowest_open_move:.2f}%")

    else:
        print("\nNo events to summarize.")

def write_index():
    links = []
    for f in sorted(OUTPUT_DIR.glob("*.html")):
        if f.name == "index.html":
            continue
        links.append(f'<li><a href="{f.name}">{f.stem}</a></li>')

    html = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Ticker Runs</title></head>
<body>
<h1>Ticker Runs</h1>
<ul>
{''.join(links)}
</ul>
</body>
</html>
"""
    (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")
        
if __name__ == "__main__":
    from io import StringIO

    buffer = StringIO()
    tee = Tee(sys.stdout, buffer)

    old_stdout = sys.stdout
    try:
        sys.stdout = tee
        run_analysis(ticker, fixed_threshold)
    finally:
        sys.stdout = old_stdout

    write_html(ticker, buffer.getvalue())
    write_index()
    


