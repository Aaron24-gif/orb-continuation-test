# It passed the holdout. We killed it anyway.

An opening-range breakout continuation strategy on index CFDs: buy the first break of the
09:15–09:30 New York range, stop at the other side of the range, hold to the close.

It was tested in-sample, then on a validation window, and was **killed there**. Nine months later,
after a bug fix changed what we believed about one of its columns, one pre-registered look at
untouched data was spent on a Nasdaq-only version.

**On 17 months of data no version of the idea had ever seen, it made money: profit factor 1.357,
+0.30R per trade over 351 trades.** It still does not pass the bar to trade, and this repository is
everything needed to check both halves of that sentence.

The interesting part is not the verdict. It is that "passed the final test" and "good enough to
trade" are different questions, and that two engine bugs were caught on the way — one of which made
the result *worse* when fixed, which is how you know the original kill was not a bug artefact.

---

## The result

**The one-shot holdout, Nasdaq only, entries 2025-01-01 → 2026-05-21**, pre-registered on
2026-09-16 before any data after 2024 was loaded, run once:

| fill | n | win % | profit factor | per trade | t |
|---|---|---|---|---|---|
| **at the level, 1× spread** | 351 | 19.4 | **1.357** | **+0.304R** | 1.75 |
| at the level, 2× spread | 351 | 19.4 | 1.274 | +0.246R | 1.42 |
| +1 minute late, 1× spread | 330 | 21.5 | 1.450 | +0.376R | 1.57 |
| +1 minute late, 2× spread | 330 | 21.5 | 1.345 | +0.307R | 1.29 |

Both calendar years positive at both bounds. The pre-registered pass rule was "mean net R above zero
at 1× spread, and if both fill bounds agree the verdict is final" — they agreed. **Holdout: pass.**

**The acceptance bar, over the whole record** — in-sample, validation and holdout together, Nasdaq,
filled at the level:

| | n | win % | profit factor | per trade | t | max drawdown | years positive |
|---|---|---|---|---|---|---|---|
| 1× spread | 2,138 | 17.0 | 1.248 | +0.232R | 2.89 | 66.1R | 8 of 9 |
| **2× spread** | 2,138 | 16.9 | **1.095** | +0.099R | 1.23 | **128.3R** | 6 of 9 |

| criterion, fixed in advance | result | |
|---|---|---|
| at least 400 trades | 2,138 | **pass** |
| profit factor ≥ 1.25 at 2× spread | **1.095** | **fail** |
| positive in ≥ 6 of the 9 calendar years at 2× | 6 of 9 | pass |
| maximum drawdown under the bar | **128.3R at 2×** (66.1R at 1×) | **fail** |
| positive on the untouched holdout, once | +0.304R | pass |
| parameter neighbourhood re-checked | not re-run | — |
| reconciled trade-for-trade against a live feed | not started | — |

Drawdown is in **R** — multiples of the risk on one trade. The bar it is measured against is a
percentage of capital at a fixed notional risk per trade, which is a protocol convention and not a
statement about anyone's position sizing, so the honest unit to publish is R.

**Verdict: the edge survived a clean holdout and still fails the bar to trade.** Too thin at doubled
costs, and too deep in drawdown for a strategy that wins 17% of its trades.

## The sharpest thing in the data

"It passed the holdout and failed the bar" is true but soft. The data says something harder:

> **At normal costs the Nasdaq version earns +0.23R per trade over eight years. Double the spread
> and it earns almost nothing — over 2018–2022 it was +0.004R, a profit factor of 1.004. The entire
> edge is roughly the size of one extra spread at the open.**

Which is exactly the quantity that had never been measured. Hence `probe/`, and hence the rest of
this README.

Two supporting points, both from the files:

- The holdout pass rule only asked *is it positive?* At t = 1.75 it would not have cleared a
  significance bar on its own. The acceptance bar asks a different question — does it survive
  doubled costs and a survivable drawdown — and there the answer is no.
- Fixing the second bug made the one-minute-late validation column **worse** (profit factor 1.027 →
  1.012). The original kill was not an artefact of the bug.

## The three windows, in order

| window | what it was | pooled profit factor at 1× | what happened |
|---|---|---|---|
| **in-sample 2018–2022** | both instruments, 2,538 trades | 1.171 (corrected) | passed every pre-registered gate |
| **validation 2023–2024** | both instruments, 1,019 trades | 1.175 | **killed** — see below |
| **holdout 2025 → May 2026** | Nasdaq only, 351 trades | 1.357 | passed, once |

In-sample it cleared the bar: profit factor 1.171 after correction, 4 of 5 years positive, no year
over 50% of the profit, both instruments individually profitable, and the real result at the 100th
percentile of a 500-seed direction-shuffled placebo (placebo median 1.043, 95th percentile 1.132).

**That placebo was run on the pre-correction figure of 1.240, and was never re-run on the corrected
series.** The argument that it still holds — the real and placebo runs shared the same blind spot
symmetrically — is an argument, not a recomputed number. It is listed as a gap rather than quietly
left out.

Validation then broke two of the gates that in-sample had cleared, which is why it was killed there:

1. **The one-minute-late fill nearly collapsed**: profit factor 1.178 in-sample against **1.012** in
   validation. Lagging the fill by the one full minute a real order might face left it at
   break-even. That is the most important number on the whole study.
2. **The Dow fell below break-even** (0.972), failing the both-instruments gate that was written in
   precisely because this was a second bet on one population.
3. **71.7% of the two-year profit came from 2024 alone** — the single-period shape the acceptance bar
   exists to catch.

The holdout look was spent later, on the Nasdaq-only configuration, with that history declared: it
is the **fourth** look at this population, and the choice of configuration was made *after* seeing
which instrument failed. `PREREG.md` §6 and §8 carry the full ledger, because a holdout result is
only worth what the count of previous looks allows.

## The two bugs, and the check that caught both

**A check worth stealing: if the win rate and the gross result disagree in sign, you have a bug.** A
strategy winning 44% of 1:1 trades cannot be profitable before costs. The protocol also treats *a
deliberately worse fill outperforming a better one* as a bug report rather than a finding. Both bugs
here were caught by those rules before anyone read a verdict.

**Bug 1 — same-minute stop-outs were invisible.** About 11% of in-sample trades had the violent
entry bar itself touch the stop after the fill. The exit scan started on the next bar, so those
losses were never booked. Correcting it under the adverse-first convention moved the pooled profit
factor from 1.240 to **1.153–1.171** (a band from two independent recomputations; 1.171 is what the
saved corrected file reproduces). In the validation and holdout engines the check runs *inside* the
simulator, before the forward scan, rather than as a correction afterwards.

**Bug 2 — the entry could land on the wrong side of its own stop.** In the one-minute-late column
only, when price traversed the entire opening range inside the break minute, the late entry sat
beyond the stop, and the engine then booked the stop-out as a *profit*:

| window | affected | wrongly booked | per trade before → after | profit factor before → after |
|---|---|---|---|---|
| validation, pooled | 20 of 1,019 | +12.7R | +0.023R → **+0.011R** | 1.027 → **1.012** |
| holdout, pooled | 35 of 699 | +16.0R | +0.311R → +0.303R | 1.387 → 1.364 |
| holdout, Nasdaq | 21 of 351 | +10.4R | +0.383R → +0.376R | 1.481 → 1.450 |

At-level fills cannot have this bug — zero cases in every at-level file. A trader would not hold a
long below its own stop, so those rows are dropped rather than repriced, and the count is reported
rather than absorbed.

**And one inversion that was not a bug.** In the holdout the late fill beat the at-level fill, which
is a red flag by protocol. The explanation is in the data: in 49 of 351 at-level trades (14.0%, up
from 6.8% in validation) the break minute also touched the opposite extreme, and the adverse-first
convention scores all of those as stop-outs, worth −52.5R. The late fill enters after that minute
and never sees them. So the at-level column is a conservative bound, the late column is not an upper
bound, and the true number sits between two conventions that 1-minute bars cannot separate. Which
is, again, an argument for measuring real fills.

## How much slippage it survives

Everything above assumes you get filled at your stop level. The strategy rests stop orders at the
cash open, the worst moment of the day for that assumption.

`src/reprice.py` answers the question arithmetically: take the saved validation trades, move each
entry against the trade point by point, leave the stop and the exit where they are, and recompute.
A worse entry cannot turn a stop-out into a survivor, and the close-out is a fixed price, so this is
arithmetic on a blotter and not a new backtest.

| entry slippage | pooled PF | pooled per trade | Nasdaq PF | Nasdaq per trade |
|---|---|---|---|---|
| 0.00 pts | 1.175 | +0.151R | 1.359 | +0.322R |
| 1.00 | 1.122 | +0.105R | 1.287 | +0.257R |
| 1.80 | 1.084 | +0.072R | 1.235 | +0.210R |
| **3.20** (the measured one-minute delay) | 1.023 | +0.019R | 1.154 | +0.137R |
| 5.00 | 0.954 | −0.040R | 1.064 | +0.057R |

**Break-even slippage: 3.76 points pooled, 6.47 points on the Nasdaq alone, both at 1× spread
(4.70 on the Nasdaq at 2×).** On the holdout trades the same arithmetic gives 10.28 points.

And a measured fact next to it: **filling one minute late costs about 3.2 points** on average, 2.1 at
the median. So the honest verdict on executability sits somewhere between fragile and dead,
depending on the fills you can actually get.

## The measurement that was built and never taken

`probe/` is an expert advisor that rests minimum-size stop orders on **both** sides of the opening
range every session and closes anything that fills immediately. It measures the one quantity the
whole study turns on: real slippage on a stop order at the open. It has no edge and is expected to
lose its own costs — it is metrology, not a strategy.

The decision bands (≤ 0.60 points, 0.60–1.80, > 1.80) and the stopping rule were fixed before a
single fill existed, in `PREREG.md` §9, specifically so that a good-looking mean with a wide
confidence interval could not be read as an answer.

**Fills collected: 0.**

The most useful thing in this repository has no results. That is published as readily as the rest of
it, because the alternative — quoting a strategy's executability from a stand-in nobody measured —
is how the first version of this study talked itself into a pass.

## Running it

```bash
pip install -r requirements.txt
# put your own MT5 exports in data/ - see data/HOWTO.md

python src/orb_insample.py      # 2018-2022: primary, brackets, gold diagnostic, 500-seed placebo
python src/orb_validation.py    # 2023-2024: both frozen configs, same-minute check built in
python src/orb_holdout.py       # 2025 -> 2026-05-21, Nasdaq decisive

python src/evaluate.py          # reads the saved blotters only: bugs, bounds, acceptance bar
python src/reprice.py           # the slippage decision table
```

`src/evaluate.py` and `src/reprice.py` read the committed files in `results/` and need no data at
all, so the headline numbers in this README can be reproduced from a clone in a few seconds. The
three engine scripts need the price data.

The in-sample script is the slow one: the 500-seed placebo re-simulates every trade 500 times.

No data is included — it is not ours to redistribute. `data/HOWTO.md` has the export recipe and the
three mistakes that will otherwise break your reproduction, one of which (the spread column's units)
will make the strategy look profitable when it is not.

## Files

| | |
|---|---|
| `PREREG.md` | the rules, the pass marks, the look-count ledger and the kill conditions, each dated |
| `src/orb_insample.py` | 2018–2022: the strategy, the neighbourhoods, the direction-shuffled placebo |
| `src/orb_validation.py` | 2023–2024, both frozen configurations, same-minute check native |
| `src/orb_holdout.py` | the one-shot window, with a hard assertion against the sealed period |
| `src/evaluate.py` | applies the pre-registration to the holdout: bugs first, then the verdict |
| `src/reprice.py` | the slippage decision table, computed before any fill existed |
| `src/data.py` | the data seam |
| `probe/SlippageProbe.mq5` | the expert advisor that measures real fills |
| `probe/analyse_fills.py` | reads its output and applies the pre-set bands |
| `probe/RUNBOOK.md` | how to run it, and the stopping rule |
| `results/` | every trade blotter, the run logs, the evaluation output, the equity curve |

The three engine scripts are near-copies of each other. That is deliberate: each window got its own
frozen file rather than a shared one with a date switch, so that a later window could not silently
change an earlier result. The duplication is the audit trail.

In `results/`, the file names follow the programme's stage names: no suffix is in-sample, `S3/` is
validation, `S4/` is the holdout. `POOLED_primary_CORRECTED_samebarSL.csv` is the in-sample series
after bug 1; `*_detectability.csv` are the one-minute-late columns; `*_A014b_*` are the volume-filter
configuration; `POOLED_2R_bracket.csv` and `POOLED_1.5R_bracket.csv` are the exit neighbourhoods,
which fail — and fail for a coherent reason, since a 17% win rate with a positive expectancy is a
system whose edge lives in the tail that a bracket clips.

## Honesty notes

- Every pass mark and kill condition in `PREREG.md` was written **before** the window it applies to
  was read. The dates are in the file. A bar chosen afterwards would make all of this decoration.
- **The in-sample placebo was never re-run on the corrected series.** Listed above as a gap.
- The holdout was the **fourth** look at this population and the configuration was chosen after
  seeing which instrument failed. Declared in `PREREG.md` §6 and §8. A holdout is worth what the
  count of previous looks allows, and this one carries a surcharge.
- Two bugs in our own code each produced a flattering result before they were found. They are logged
  with their magnitudes rather than quietly fixed.
- The programme's sealed out-of-sample period is refused by an assertion in the loader. 2025+ is now
  spent for this entire family of ideas, which is why no amount of re-running this repository will
  produce a new verdict for us. It may well produce one for you, on your own data.
- This is research code, published because the strategy does not clear the bar to trade. It is not a
  trading system, it is not advice, and nothing here is a recommendation.

**MIT. Take it.** The two things we would most like back: a measured slippage distribution for stop
orders at the cash open on any index CFD, and an argument that our same-minute convention is wrong
in either direction.
