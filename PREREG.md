# Pre-registration — opening-range breakout continuation

**Registered 2026-07-19**, before the strategy was run. The holdout section was registered
**2026-09-16**, before any data after 2024 was loaded by any version of this code.

This file exists so that the verdict cannot be argued with afterwards. It fixes the rules, the pass
marks, the number of looks and the kill conditions in advance. Every date below is the date the
decision was written down, not the date it was convenient to claim.

---

## 1. Hypothesis, in one falsifiable sentence

Entering **with** the first breach of the 09:15–09:30 New York opening range that occurs during
09:30–09:45, with the stop at the opposite extreme of that range, held to the session close, is net
profitable after real spread on the Nasdaq and Dow index CFDs over 2018–2022, and beats a
direction-shuffled placebo at the 95th percentile.

Source of the idea: Zarattini, Barbon and Aziz, *A Profitable Day Trading Strategy for the US Equity
Market* — a 5-minute opening-range breakout on single stocks, with the result concentrated in names
trading unusual volume. This is our own implementation on index CFDs; none of their code is used or
redistributed here.

## 2. The honesty declaration that comes first

**This is the second directional bet spent on the same population of events** (one-sided 09:30–09:45
breaks). The first was the opposite bet — fading those breaks — and it was unanimously negative.

**A failed reversal bet does not imply a working continuation bet.** A mirrored bet does not get a
mirrored geometry for free: both directions can lose to chop plus cost, and in this case both do
lose at some configurations. This card stands on the published literature, not on the corpse of the
previous one.

Because it is a second look at one population, the success bar carries a surcharge: the placebo gate
**and** a requirement that both instruments are individually profitable. Stated before the run, not
negotiated after it.

One further warning recorded at registration: a sibling test of first-half-hour momentum on these
same instruments was gross-negative. Different mechanism, same instruments — noted rather than
ignored.

## 3. Knowability map

| Object | Anchor | Confirmed | Available from | Earliest executable |
|---|---|---|---|---|
| Range high / low | 09:15–09:30 bars | window close 09:30 | 09:30 | stop orders armed at 09:30 |
| First break | first M1 bar breaching either extreme in 09:30–09:45 | intrabar touch | at touch | filled at the level, or the bar's open if price gaps through it; the other side's order cancels on fill |
| Exit | session close, or the stop | — | — | gap-aware forced flat |

**First-break-wins, decided causally.** The day's direction is set by the *first* breach. A later
breach of the other side is the stop or the whipsaw playing out — it never retrospectively voids the
day. This rule exists because the previous card on this population applied a both-sides-void rule
*retrospectively*, which quietly removed whipsaw days with hindsight, in the flattering direction.

Leak checklist: the range is fully closed before the orders are armed; the levels are fixed at
09:30; fills are genuine intrabar touches; the day is stateless; window-validity guards require at
least 80% of the expected bars in both the range and the permit window; the exit scan starts from
the fill bar so there is no unscanned exposure.

## 4. Full specification

1. **Valid day**: at least 80% of expected 1-minute bars present in the range window and the permit
   window. Otherwise no trade.
2. **Range**: high and low of 09:15–09:30 New York.
3. **Entry**: at 09:30, a buy-stop at the range high and a sell-stop at the range low, both valid
   until 09:45. First fill wins, the other cancels. No fill by 09:45 means no trade that day.
4. **Stop**: the opposite extreme of the range, so risk is approximately the range width. Skip the
   day if that distance is below 0.3× or above 3× ATR(14) of 15-minute bars.
5. **Exit**: no target. Held to the session close, with the stop active throughout. This is the
   literature-faithful exit and is the primary configuration.
6. **One trade per day per instrument.**
7. **Costs**: the broker's real per-bar spread charged at both fills, so the spike at the open is
   paid rather than averaged away. No commission (index CFDs), no financing (every trade closes the
   same day). A doubled-spread column is computed everywhere as a stress test.
8. **Same-minute rule**: if the stop is touched inside the minute the trade filled, it counts as a
   stop-out. 1-minute bars cannot say which came first, so the convention is the adverse one.

## 5. Parameters and their neighbourhoods

| Parameter | Value | Neighbourhood tested |
|---|---|---|
| Break window | 09:30–09:45 (inherited from the previous card, not searched) | extend to 10:00 |
| Exit | hold to close (literature) | 2R and 1.5R brackets |
| Stop | opposite range extreme | 0.5 × range |
| Range window | 09:15–09:30 (the source's convention) | **fixed, not searched** |
| Entry offset | 0, at the level | +0.05 ATR |

## 6. Multiple-testing ledger — every look, counted

1. **The primary configuration**, run 2026-07-19. The bracket neighbourhoods, the gold diagnostic
   and the 500-seed placebo are part of the same run.
2. **A relative-volume filter, registered 2026-07-20 — after the volume diagnostic had been seen.
   The snooping is declared, not hidden.** Take the primary trade only when the opening range's mean
   tick volume is at least 0.8602 × the trailing 20-day median. One threshold, frozen at the
   in-sample 33.3rd percentile, never re-optimised: no scan over cutoffs, no second filter, no
   stacking. The motivation is external (the source paper's volume conditioning) and the split was
   pre-specified as a diagnostic — but the *direction* of the filter was chosen after seeing the
   result. Mitigation: it counts as a second configuration, it must survive validation and the
   holdout unchanged alongside the primary, and if it underperforms the primary out of sample that
   is evidence the split was noise and gets recorded as such.
3. **The holdout look**, registered 2026-09-16 (section 8 below). Nasdaq-only. That makes it the
   **fourth** look at this population, chosen after validation showed the Dow below break-even. The
   surcharge is stated there and carried into the verdict.

## 7. Pre-registered success criteria, written before the first run

**In-sample bar (2018–2022):**

- profit factor ≥ 1.15 net at 1× real spread
- at least 300 pooled trades
- at least 4 of the 5 years positive
- no single year contributing more than 50% of the profit
- **both instruments individually above break-even** — the second-bet surcharge
- at or above the 95th percentile of a 500-seed direction-shuffled placebo: identical fills, risk
  and exits, with the direction replaced by a coin flip

**Reported, never selected on:** relative tick-volume terciles, the break-side split, range-size
quartiles against outcome, the distribution of break times, by-year, by-weekday, the gold diagnostic
on a different session convention, and the excursions of the held-to-close trades.

**Out-of-sample bar:** the programme's acceptance bar, and the 2025+ holdout looked at once.

## 8. Holdout pre-registration — written 2026-09-16, before any data after 2024 was loaded

**The decision, declared openly:** the one holdout look is spent on a **Nasdaq-only**
configuration. That is the fourth look at this population, and it was chosen *after* validation
showed the Dow below break-even. One configuration is all the protocol allows at this stage, and
this is it.

- **Configuration**: the primary rules exactly as frozen on 2026-07-19, Nasdaq only, no volume
  filter. The engine is the validation script with nothing changed but the window and the output
  folder.
- **Window**: entries 2025-01-01 → 2026-05-21. Data is loaded from 2024-11-01 purely to warm up the
  ATR and the 20-day volume median, both of which only ever look backwards. **A hard assertion
  refuses any bar dated 2026-05-22 or later**, because the programme's sealed period starts there.
- **Both fill bounds are computed**: (A) filled at the level, on the signal bar; (B) filled at the
  next minute's open. A measured slippage number selects the operative point between them, by the
  same arithmetic re-pricing as `src/reprice.py` applied to the holdout trades.
- **Pass criterion**: Nasdaq mean net R above zero at 1× spread at the operative fill. **If bounds A
  and B agree, the verdict is final that day.** If they disagree, the verdict is recorded as pending
  the slippage measurement and resolved mechanically when it arrives — no re-run, no second look.
- **The full acceptance bar is reported alongside and is not waived**: profit factor ≥ 1.25 at 2×
  spread; at least 400 Nasdaq trades counting all three windows; positive in at least 6 of the 9
  calendar years; maximum drawdown under 20% at a fixed 1% risk per trade. Known going in:
  validation's Nasdaq figure at 2× spread was already below that profit-factor bar.
- **Descriptive only, no verdict**: the Dow, the pooled version, and the volume filter on the same
  window.
- **Red flags that mean "find the bug before reading the verdict"**: profit factor above 3, more
  than 0.5R per trade, every month positive, or the deliberately worse fill outperforming the better
  one.
- After this run, **2025+ is spent for this entire family of ideas.**

## 9. The slippage measurement, and its decision table

The strategy enters on stop orders at the moment of the cash open, which is the single worst moment
of the day for slippage. The one-minute-late fill used as a stress test is a crude stand-in for
that. The real number is measurable, and `probe/` measures it.

**The decision table was computed before a single fill was collected** (`src/reprice.py`): the
validation trades re-priced with the entry moved against the trade point by point, stop and exit
unchanged. Pure arithmetic on a saved blotter, not a re-run.

**Bands fixed in advance:**

| measured mean slippage | verdict |
|---|---|
| ≤ 0.60 points | fills are near-level |
| 0.60 – 1.80 points | partial; decided by the re-priced Nasdaq figure at 2× spread |
| > 1.80 points | the kill is confirmed, the family closes |

**Stopping rule, amended 2026-09-16 before any fill existed:** an early stop is allowed from 20
fills only if the 95% bootstrap interval of the mean sits entirely on one side of a band edge;
otherwise it runs to a floor of 60 fills. **Not stopping on a good-looking mean whose interval still
straddles a threshold is the whole point of writing this down.**

## 10. What would have changed our mind

Profit factor at or above 1.25 at doubled spread over the full record, with the drawdown bar met and
the holdout positive. The holdout *was* positive. The other two were not, and that is the verdict.
