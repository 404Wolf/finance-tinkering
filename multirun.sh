#!/usr/bin/env bash

set -euo pipefail

TICKERS_FILE="goodfebtick.txt"

if [[ ! -f "$TICKERS_FILE" ]]; then
  echo "Error: $TICKERS_FILE not found" >&2
  exit 1
fi

while IFS= read -r ticker || [[ -n "$ticker" ]]; do
  # skip empty lines and comments
  [[ -z "$ticker" || "$ticker" =~ ^# ]] && continue

  echo "Running earnings analysis for $ticker"
  printf 'Ticker raw: [%q]\n' "$ticker"
  uv run -m src.earnings_analysis "$ticker" --ft 3
done < "$TICKERS_FILE"