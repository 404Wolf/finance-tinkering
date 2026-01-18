import csv
import re
from pathlib import Path

INPUT_DIR = Path("output/")   # folder with the html files
OUTPUT_CSV = Path("earnings_summary_febold.csv")

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)

MIN_SPIKE_RE = re.compile(r"Minimum Spike:\s*([-\d.]+)%")
AVG_SPIKE_RE = re.compile(r"Average Spike:\s*([-\d.]+)%")
MEDIAN_SPIKE_RE = re.compile(r"Median Spike:\s*([-\d.]+)%")
EARNINGS_COUNT_RE = re.compile(r"Earnings Count:\s*(\d+)")

# Matches *each* threshold block
THRESHOLD_BLOCK_RE = re.compile(
    r"---.*?Threshold ---\s*"
    r"Hits:\s*(\d+)/(\d+)\s*"
    r"Conditional result:\s*([-\d.]+)\s*"
    r"Average Loss \(threshold not met\):\s*([-\d.]+)%"
    r".*?",
    re.DOTALL
)

def parse_file(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")

    def extract(regex, cast=str):
        m = regex.search(text)
        return cast(m.group(1)) if m else None

    ticker = extract(TITLE_RE, str)
    min_spike = extract(MIN_SPIKE_RE, float)
    avg_spike = extract(AVG_SPIKE_RE, float)
    median_spike = extract(MEDIAN_SPIKE_RE, float)
    earnings_count = extract(EARNINGS_COUNT_RE, int)

    # Find all threshold blocks and take the *last* one
    blocks = THRESHOLD_BLOCK_RE.findall(text)
    if not blocks:
        return None

    hits, _, conditional_result, avg_loss = blocks[-1]

    return {
        "ticker": ticker,
        "conditional_result": float(conditional_result),
        "earnings_count": earnings_count,
        "hits": int(hits),
        "avg_loss_threshold_not_met": float(avg_loss),
        "min_spike": min_spike,
        "avg_spike": avg_spike,
        "median_spike": median_spike,
    }

def main():
    rows = []

    for html_file in INPUT_DIR.glob("*.html"):
        row = parse_file(html_file)
        if row:
            rows.append(row)

    if not rows:
        print("No valid HTML files found.")
        return

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
