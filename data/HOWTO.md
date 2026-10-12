# Getting data in

One MetaTrader 5 M1 export per instrument in this folder, named `<INSTRUMENT>.csv`, tab separated,
exactly as the terminal writes it:

```
<DATE>	<TIME>	<OPEN>	<HIGH>	<LOW>	<CLOSE>	<TICKVOL>	<VOL>	<SPREAD>
2018.01.02	16:15:00	6534.1	6535.8	6533.9	6535.2	412	0	14
```

The study used `USTEC.csv` (Nasdaq 100 CFD) and `US30.csv` (Dow CFD) for everything, plus
`XAUUSD.csv` for a side diagnostic on a different session convention. Instrument names come from the
`DATA` dict at the top of each engine script.

## Exporting

1. Tools → Options → Charts → "Max bars in chart": set to Unlimited, then restart the terminal.
2. Open the symbol on M1 and hold Home until the history has downloaded back to your start date. The
   export only contains what the terminal actually has.
3. Tools → History Center (F2) → pick the symbol and M1 → Export.

Keep the header row and the tab separators. The loader reads these files in 50,000-row chunks and
filters on the raw date string, because a full M1 history runs to several hundred megabytes.

## The three things that will break your reproduction

**1. `<SPREAD>` is in POINTS, not price.** It is multiplied by the instrument's point size in
`src/data.py`:

```python
POINT = {"USTEC": 0.01, "US30": 0.01, "XAUUSD": 0.01}
```

Those are right for a 2-digit index CFD feed. On a 5-digit FX feed it is 0.00001. **Getting this
factor wrong by a power of ten is the single easiest way to make this strategy look profitable** —
the whole edge is about the size of one spread at the open, so dividing the cost by ten manufactures
one.

A second warning, from elsewhere in the same programme: on several feeds `<SPREAD>` is a **posted
tariff** rather than a measured one. It sits at a constant value for years and tells you nothing
about real liquidity. Check whether yours actually varies before trusting any cost-sensitive result,
and note that index CFD costs fell by roughly a factor of seven between 2018 and 2026 — which is why
the 2× stress column matters more in the early years than the late ones.

**2. The timestamps are the broker SERVER's clock, not New York's.** Every window in the strategy is
expressed in that server clock. At the top of each engine script:

```python
CONVENTIONS = {"stock": (16, 15, 16, 30, 16, 45)}   # range start, range end, permit end
```

That is 16:15–16:30 and 16:45 **server time**, on a server running 7 hours ahead of New York —
which is how 09:15–09:30 ET and a window to 09:45 ET are expressed. The code does no timezone
conversion at all: it trusts the timestamps.

So if your server is not at that offset, either convert the timestamps on export or shift those six
numbers. A silently shifted opening range still produces trades — just not the ones the study tested,
and usually better-looking ones, because a range taken from a quiet hour breaks more cleanly.

The `DAY_BOUNDARY` of 23:00 and the forced flat at 23:00 are in the same server clock.

**3. Your `<VOL>` column is almost certainly zeros.** A broker streaming a CFD cannot know the
traded volume of an exchange it is not part of. `<TICKVOL>`, the number of price updates in the bar,
is what the volume-filter configuration uses, and the loader reads that one. That is a deliberate
choice, not an oversight, and the filter's threshold is expressed as a ratio to its own trailing
20-day median so that the units cancel.

## Checking it loaded correctly

```python
from data import load_m1
d = load_m1("USTEC.csv", "2018.01.02", "2018.01.31")
print(len(d), d.ts.min(), d.ts.max(), d.spread_price.median())
```

The median spread should be a plausible price distance for the instrument — on the Nasdaq CFD a
fraction of a point to a couple of points, not hundreds and not 0.0001. If it is out by a factor of
ten, fix `POINT` before you run anything.

Then check that an opening range looks like one:

```python
day = d[d.ts.dt.normalize() == d.ts.dt.normalize().iloc[0]]
r = day[(day.ts.dt.hour == 16) & (day.ts.dt.minute >= 15) & (day.ts.dt.minute < 30)]
print(len(r), r.high.max() - r.low.min())
```

15 bars, and a range that is a sensible fraction of the day's range. If you get 0 bars, your server
offset is different and point 2 applies.

## What the study used

Two index CFDs from one broker, 1-minute bars, 2018-01-01 → 2026-05-21, with the period after that
sealed and refused by an assertion in the loader. No data is included in this repository; it is not
ours to redistribute.
