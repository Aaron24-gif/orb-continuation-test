"""
M-001 ANALYSER — applies the card's pre-registered decision rule to measured fills.

Usage:  python analyse_fills.py <path to m001_fills.csv> [<m001_days.csv>]

Decision rule, fixed in cards/M-001_orb_slippage_metrology.md BEFORE collection, converted
to R with A-014's in-sample mean risk of 29.85 index points:
    mean slip <= 0.60 pts (slip_R <= 0.02)  -> fills are near-level
    0.60 < mean slip <= 1.80 pts            -> partial; read the re-priced table
    mean slip  > 1.80 pts (slip_R > 0.06)   -> the kill stands, family closed

Nothing here re-runs a backtest: the validation trades are re-priced arithmetically at the
measured slippage (same method as src/reprice.py, which was computed before any fill existed).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from reprice import S3, reprice, row  # noqa: E402

MEAN_RISK_PTS = 29.85          # A-014 in-sample mean risk, used by the card to convert pts -> R
FLOOR_FILLS = 60               # full-sample floor (card)
MIN_EARLY = 20                 # AMENDMENT 2026-09-16: earliest an early stop may be taken
BOOT = 20000                   # bootstrap resamples for the CI of the mean


def boot_ci(x, alpha=0.05, seed=12345):
    """Percentile bootstrap CI of the MEAN. Slippage is right-skewed, so a normal CI understates."""
    r = np.random.default_rng(seed)
    idx = r.integers(0, len(x), size=(BOOT, len(x)))
    m = np.asarray(x, float)[idx].mean(axis=1)
    return float(np.quantile(m, alpha / 2)), float(np.quantile(m, 1 - alpha / 2))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    f = pd.read_csv(sys.argv[1])
    f.columns = [c.strip() for c in f.columns]
    n = len(f)
    print("=" * 96)
    print(f"  M-001 — measured stop-order fills at the US cash open   (n = {n})")
    print("=" * 96)
    if n == 0:
        print("  no fills logged yet")
        return 0

    slip = f["slip_pts"].astype(float)
    print(f"  entry slippage pts : mean {slip.mean():+.2f}  median {slip.median():+.2f}  "
          f"p90 {slip.quantile(0.9):+.2f}  max {slip.max():+.2f}  worse-than-level {100*(slip>0).mean():.0f}%")
    print(f"  as a fraction of 1R: mean {slip.mean()/MEAN_RISK_PTS:+.4f} "
          f"(card thresholds 0.02 / 0.06 = 0.60 / 1.80 pts)")
    for col, lab in (("delay_sec", "fill delay sec"), ("spread_at_fill_pts", "spread at fill pts"),
                     ("exit_slip_pts", "exit slippage pts")):
        if col in f:
            c = f[col].astype(float)
            print(f"  {lab:<19}: mean {c.mean():+.2f}  median {c.median():+.2f}  max {c.max():+.2f}")
    if "side" in f:
        print("  by side:", {k: round(v, 2) for k, v in slip.groupby(f["side"]).mean().items()})
    if len(sys.argv) > 2 and Path(sys.argv[2]).exists():
        d = pd.read_csv(sys.argv[2])
        print(f"  days logged {len(d)}, days with orders placed {int((d['placed'] > 0).sum())}, "
              f"fills per placing day {n / max(1, int((d['placed'] > 0).sum())):.2f}")

    lo, hi = boot_ci(slip.to_numpy(float))
    print(f"  95% bootstrap CI of the mean: [{lo:+.2f}, {hi:+.2f}] pts")

    # AMENDMENT 2026-09-16, fixed before any fill existed: an EARLY STOP is allowed once the whole
    # CI sits inside one band, but never before MIN_EARLY fills. It cannot produce a verdict the full
    # sample would contradict at the 95% level, and it ends the study in ~2 weeks when the answer is
    # obvious either way. Anything ambiguous still runs to the 60-fill floor.
    early = None
    if n >= MIN_EARLY:
        if hi <= 0.60:
            early = "NEAR-LEVEL - the whole CI is below 0.60"
        elif lo > 1.80:
            early = "KILL CONFIRMED - the whole CI is above 1.80"
    if n < FLOOR_FILLS and early is None:
        need = ("the CI to clear a band" if n >= MIN_EARLY
                else f"{MIN_EARLY - n} more fills before an early stop is allowed")
        print(f"\nNO VERDICT YET at {n} fills. Keep collecting: need {need}, "
              f"or {FLOOR_FILLS - n} more to reach the floor.")
        return 0
    if early:
        print(f"\nEARLY STOP AVAILABLE at n={n}: {early}")

    s = float(slip.mean())
    print("\n  Re-pricing the A-014 validation trades (2023-24) at the measured slippage:")
    d = pd.read_csv(S3 / "POOLED_S3_primary.csv")
    u = d[d.instrument == "USTEC"]
    for lab, dd in (("POOLED", d), ("USTEC", u)):
        a, b = row(reprice(dd, s, "cost_1x")), row(reprice(dd, s, "cost_2x"))
        print(f"    {lab:<7} n={a['n']:<5} 1x: PF {a['pf']:.3f} meanR {a['meanR']:+.3f} t {a['t']:+.2f}"
              f"   |  2x: PF {b['pf']:.3f} meanR {b['meanR']:+.3f}")

    print("\n  VERDICT (card rule):")
    if s <= 0.60:
        print(f"    mean slippage {s:.2f} pts <= 0.60 -> fills are NEAR-LEVEL. A-014's kill rested on")
        print("    the pessimistic bound. A USTEC-only card may be registered, with the 4th-look")
        print("    surcharge declared, and it must clear the untouched 2025+ holdout in one shot.")
    elif s <= 1.80:
        print(f"    mean slippage {s:.2f} pts is in the PARTIAL band. The decision falls out of the")
        print("    USTEC 2x PF above: >= 1.25 registers a new card, below it the family stays closed.")
    else:
        print(f"    mean slippage {s:.2f} pts > 1.80 -> KILL CONFIRMED. A-014 and the ORB")
        print("    continuation family are closed for good; record it and spend no more on them.")
    print("\n  Note carried from the pre-computed table: even at ZERO slippage the USTEC 2x PF on")
    print("  validation is 1.240, just under the 1.25 acceptance bar — so a near-level result")
    print("  clears the EXECUTION doubt only; the edge itself would still have to prove out on the")
    print("  2025+ holdout. Demo fills also flatter live fills, so a good number here is necessary,")
    print("  not sufficient.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
