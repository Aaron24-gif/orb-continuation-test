"""The data seam. One MetaTrader 5 M1 export per instrument in `data/`, tab separated, exactly as
the terminal writes it:

    <DATE>	<TIME>	<OPEN>	<HIGH>	<LOW>	<CLOSE>	<TICKVOL>	<VOL>	<SPREAD>
    2018.01.02	16:15:00	6534.1	6535.8	6533.9	6535.2	412	0	14

No data is included in this repository; it is not ours to redistribute. `data/HOWTO.md` has the
export recipe and the three things that will otherwise break your reproduction.

Two facts this loader depends on, both documented in HOWTO:

- **`<SPREAD>` is in POINTS, not price.** It is multiplied by the instrument's point size below.
  Getting that factor wrong by ten is the easiest way to make this strategy look profitable.
- **The timestamps are the broker SERVER's clock, not New York's.** Every window in the strategy
  is expressed in that server clock (see `CONVENTIONS` in the engine scripts), on a server running
  7 hours ahead of New York. If yours is not, convert on export or shift the windows.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"

# <SPREAD> is in points; multiply by this to get price. 2-digit index CFD feeds are 0.01.
POINT = {"USTEC": 0.01, "US30": 0.01, "XAUUSD": 0.01}

# The programme's sealed out-of-sample period begins here and is never loaded.
SEALED = pd.Timestamp("2026-05-22")

COLS = ["date", "time", "open", "high", "low", "close", "tickvol", "vol", "spread"]
USECOLS = ["date", "time", "open", "high", "low", "close", "tickvol", "spread"]
DTYPES = {"open": "float32", "high": "float32", "low": "float32", "close": "float32",
          "tickvol": "int32", "spread": "int32"}


def load_m1(fname: str, start: str, end: str) -> pd.DataFrame:
    """M1 bars for one instrument between `start` and `end`, both 'YYYY.MM.DD' strings.

    Read in chunks and filtered on the raw date string, because these exports run to several
    hundred megabytes and only a few years of any of them are ever wanted at once.
    """
    path = DATA / fname
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - see data/HOWTO.md")
    point = POINT.get(Path(fname).stem, 0.01)
    parts = []
    for chunk in pd.read_csv(path, sep="\t", names=COLS, header=0, usecols=USECOLS,
                             dtype=DTYPES, chunksize=50_000):
        m = (chunk["date"] >= start) & (chunk["date"] <= end)
        if m.any():
            sub = chunk.loc[m].copy()
            sub["ts"] = pd.to_datetime(sub["date"] + " " + sub["time"], format="%Y.%m.%d %H:%M:%S")
            sub["spread_price"] = sub["spread"] * point
            parts.append(sub[["ts", "open", "high", "low", "close", "tickvol", "spread_price"]])
        if chunk["date"].iloc[-1] > end:
            break
    if not parts:
        raise ValueError(f"{path}: no rows between {start} and {end}")
    df = pd.concat(parts, ignore_index=True)
    assert df["ts"].max() < SEALED, f"reached the sealed out-of-sample period: {df['ts'].max()}"
    df["day"] = df["ts"].dt.normalize()
    return df
