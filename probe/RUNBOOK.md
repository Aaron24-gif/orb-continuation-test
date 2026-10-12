# M-001 — measuring stop-order slippage at the US cash open

**What this answers.** A-014 (opening-range breakout continuation) was killed because its edge
disappeared when fills were delayed by one minute. That delay was a deliberately pessimistic stand-in
for real execution: the strategy rests stop orders at the broker, which fill on touch plus slippage,
not a minute later. This measures the real number. It is metrology, not a strategy — the probe has no
edge and is expected to lose its (tiny) costs.

## Before you start
- **Use a demo account, and one with nothing else running on it.** The probe rests orders on both
  sides of the opening range every session; an account already running another strategy can refuse
  them on its own position checks, and you would be measuring that instead of slippage. If you must
  share an account, set `MagicNumber` to something no other expert on it uses.
- **Set `ServerGMTOffsetHrs` to your server's offset from UTC** (many MT5 servers run at +2/+3, some
  at 0). The probe converts to New York time itself, including summer time, so this is the only clock
  input it needs - and getting it wrong is the one mistake that silently produces no fills at all.
- Minimum lot size is used by default: on a demo account a fill risks a few currency units for a few
  seconds, which is the point. This is metrology, not a strategy.

## Install
1. Copy `M001_SlippageProbe.mq5` into `MQL5\Experts\` of the terminal's data folder
   (File → Open Data Folder), then compile it in MetaEditor (F7).
2. Attach it to a **USTEC M1 chart**. Enable **Algo Trading**.
3. First day: set `EnableTrading = false` and check the Experts log prints the range and the levels it
   would use. Then set it to `true`.

## What it does each US trading day
- Builds the 09:15–09:30 ET opening range from closed M1 bars.
- At 09:30 ET places a minimum-size buy stop at the range high **and** a sell stop at the range low
  (both sides — we are measuring fills, not direction; this doubles the sample).
- Anything that fills is closed at market immediately.
- Orders expire at 09:45 ET.

## Output
Written to the terminal's **common files** folder (`File → Open Data Folder` → `..\..\Common\Files`):
- `m001_fills.csv` — one row per fill: stop level, actual fill, slippage in points, delay in seconds,
  spread at fill, exit price, exit slippage.
- `m001_days.csv` — one row per day, including days where nothing was placed and why.

## Stopping rule (amended 2026-09-16, before any data)
Run `analyse_fills.py` whenever you like — it will not hand you a verdict until one of these is true:
- **early stop, from 20 fills:** the 95% bootstrap CI of mean slippage sits entirely below 0.60 pts
  (near-level) or entirely above 1.80 pts (kill confirmed). Roughly 2 weeks if the answer is clear-cut.
- **floor, 60 fills:** anything ambiguous runs this far (~4–6 weeks) and is then read off the re-priced
  USTEC 2x PF.

Do not stop on a good-looking mean whose CI still straddles a threshold — that is the failure mode this
rule exists to prevent. If the period contains no high-volatility opens (CPI, NFP, FOMC), note it: those
are where slippage is worst and they are the reason a single quiet week is not representative.

**To halve the calendar time:** attach the probe to a **US30** chart as well. Both sides fill on almost
every session, so two symbols gives ~2.8 fills/day instead of ~1.4. USTEC still decides; US30 is
reported separately.

## Reading the result
```
python probe/analyse_fills.py "<...>\Common\Files\m001_fills.csv" "<...>\Common\Files\m001_days.csv"
```
It prints measured slippage and re-prices the A-014 validation trades at that slippage, then applies
the rule the card fixed in advance:

| measured mean slippage | verdict |
|---|---|
| ≤ 0.60 pts | fills are near-level; a USTEC-only card may be registered, and must clear the untouched 2025+ holdout in one shot |
| 0.60–1.80 pts | partial; decided by whether USTEC 2× PF ≥ 1.25 in the re-priced table |
| > 1.80 pts | kill confirmed; the ORB continuation family is closed for good |

## The table, computed before any fill existed (`src/reprice.py`)
Validation 2023-24, n = 1019 pooled / 514 USTEC:

| slippage pts | POOLED PF 1× | POOLED mean R | USTEC PF 1× | USTEC mean R | USTEC PF 2× |
|---|---|---|---|---|---|
| 0.00 | 1.175 | +0.151 | 1.359 | +0.322 | 1.240 |
| 0.50 | 1.148 | +0.127 | 1.321 | +0.288 | 1.209 |
| 1.00 | 1.122 | +0.105 | 1.287 | +0.257 | 1.180 |
| 1.80 | 1.084 | +0.072 | 1.235 | +0.210 | 1.136 |
| 3.20 (the 1-minute delay) | 1.023 | +0.019 | 1.154 | +0.137 | 1.066 |
| 5.00 | 0.954 | −0.040 | 1.064 | +0.057 | 0.988 |

Break-even slippage: pooled 3.76 pts, USTEC 6.47 pts at 1× spread, USTEC 4.70 pts at 2× spread.

**Read this before getting hopeful:** even at zero slippage, USTEC at 2× spread is PF 1.240, just under
the 1.25 acceptance bar. So the best this measurement can do is clear the execution doubt. The edge
itself would still have to prove out on the 2025+ holdout, one shot. Demo fills also flatter live fills,
so a good demo number is necessary but not sufficient, while a bad one is decisive.
