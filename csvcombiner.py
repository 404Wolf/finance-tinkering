from pathlib import Path

folder = Path("csvs/")

with open("combined_raw.csv", "w", newline="") as out:
    for csv_file in sorted(folder.glob("*.csv")):
        print(f"Appending {csv_file.name}")
        with open(csv_file, "r", newline="") as f:
            for line in f:
                if line.strip():  # skip completely empty lines
                    out.write(line)
