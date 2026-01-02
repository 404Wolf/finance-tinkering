import pandas as pd
from dotenv import load_dotenv
from joblib import Memory

memory = Memory(".cache", verbose=0)
load_dotenv()

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)
