import pandas as pd
import re
from datetime import datetime, time

df = pd.read_csv("jan2018.csv")

# Regexes
explicit_label_re = re.compile(r"\b(Before Market|After Market)\b")
datetime_re = re.compile(
    r"(\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}\s+[AP]M)"
)
date_only_re = re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})")

def extract_info(desc):
    if not isinstance(desc, str):
        return pd.Series([pd.NaT, None])

    # 1. Explicit market label (future dates)
    label_match = explicit_label_re.search(desc)
    if label_match:
        label = label_match.group(1)

        # Extract date only
        dm = date_only_re.search(desc)
        if not dm:
            return pd.Series([pd.NaT, label])

        date_str = dm.group(1)
        fmt = "%m/%d/%Y" if len(date_str.split("/")[-1]) == 4 else "%m/%d/%y"
        dt = datetime.strptime(date_str, fmt)

        return pd.Series([dt, label])

    # 2. Time-based classification (past dates)
    m = datetime_re.search(desc)
    if not m:
        return pd.Series([pd.NaT, None])

    value = m.group(1)
    fmt = "%m/%d/%Y %I:%M %p" if len(value.split("/")[-1].split()[0]) == 4 \
          else "%m/%d/%y %I:%M %p"

    dt = datetime.strptime(value, fmt)
    label = "After Market" if dt.time() >= time(15, 0) else "Before Market"

    return pd.Series([dt, label])

# Apply once, expand into two columns
parsed = df["Description"].apply(extract_info)
parsed.columns = ["_ParsedDT", "ReleaseTime"]

df["ReleaseTime"] = parsed["ReleaseTime"]
df["ReleaseDate"] = parsed["_ParsedDT"].dt.date

df.to_csv("2018out.csv", index=False)
