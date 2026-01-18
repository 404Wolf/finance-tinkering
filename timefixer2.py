import pandas as pd
import re
from datetime import datetime, time

df = pd.read_csv("jan2018.csv")

explicit_label_re = re.compile(r"\b(Before Market|After Market)\b", re.IGNORECASE)
date_only_re = re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})")

def parse_date_from_description(desc):
    if not isinstance(desc, str):
        return pd.NaT
    dm = date_only_re.search(desc)
    if not dm:
        return pd.NaT

    date_str = dm.group(1)
    fmt = "%m/%d/%Y" if len(date_str.split("/")[-1]) == 4 else "%m/%d/%y"
    try:
        return datetime.strptime(date_str, fmt).date()
    except ValueError:
        return pd.NaT

def parse_time_of_day(value):
    if not isinstance(value, str):
        return None
    s = value.strip()

    # Handle "1/18/2026 6:55" (or with seconds)
    for fmt in ("%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%m/%d/%y %H:%M", "%m/%d/%y %H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.time()
        except ValueError:
            pass

    # Handle "6:55" alone (just in case)
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.time()
        except ValueError:
            pass

    return None

def compute_release_time(desc, time_val):
    # Explicit label wins
    if isinstance(desc, str):
        lm = explicit_label_re.search(desc)
        if lm:
            # normalize capitalization
            label = lm.group(1).lower()
            return "Before Market" if "before" in label else "After Market"

    tod = parse_time_of_day(time_val)
    if tod is None:
        return None

    return "After Market" if tod >= time(15, 0) else "Before Market"

df["ReleaseDate"] = df["Description"].apply(parse_date_from_description)
df["ReleaseTime"] = df.apply(lambda r: compute_release_time(r.get("Description"), r.get("Time")), axis=1)

df.to_csv("2018out2.csv", index=False)
