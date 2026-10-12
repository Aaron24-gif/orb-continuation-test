"""
A-014 S4 evaluation — applies the section-10 pre-registration to the one-shot holdout run.

Reads only files already written by orb_holdout.py (no new look at data).

Bug handled here, found by the protocol's A/B-inversion red flag BEFORE reading the verdict:
the +1-minute (detectability) fill can land on the WRONG side of its own stop when price whips
through the whole opening range inside the break minute. The engine then "stops out" at a price
better than the entry and books a profit. A real trader would never hold a long below its own
stop, so those trades are dropped (no trade). Counted and reported, S3 and S4 alike.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

A = Path(__file__).resolve().parent.parent / "results"


def inverted(x):
    sgn = np.where(x.direction == "long", 1, -1)
    return (x.entry - x.sl).to_numpy() * sgn <= 0


def st(R, t):
    R = pd.Series(np.asarray(R, float), index=pd.to_datetime(t)).sort_index()
    w, l = R[R > 0], R[R <= 0]
    eq = R.cumsum()
    m = R.groupby(R.index.to_period("M")).sum()
    y = R.groupby(R.index.year).sum()
    return dict(n=len(R), win=100 * len(w) / len(R), pf=w.sum() / -l.sum(), meanR=R.mean(),
                t=R.mean() / (R.std(ddof=1) / np.sqrt(len(R))), totR=R.sum(),
                ddR=float((eq.cummax().clip(lower=0) - eq).max()),
                posm=f"{int((m > 0).sum())}/{len(m)}", years={int(k): round(v, 1) for k, v in y.items()})


def line(lab, s):
    print(f"  {lab:<38} n {s['n']:>4}  win {s['win']:5.1f}%  PF {s['pf']:.3f}  meanR {s['meanR']:+.3f}  "
          f"t {s['t']:+.2f}  totR {s['totR']:+7.1f}  maxDD {s['ddR']:5.1f}R  months+ {s['posm']}  {s['years']}")


def reprice(d, s, cost):
    sgn = np.where(d.direction == "long", 1.0, -1.0)
    e = d.entry.to_numpy(float) + s * sgn
    return ((d.exit.to_numpy(float) - e) * sgn - d[cost].to_numpy(float)) / np.abs(e - d.sl.to_numpy(float))


def main():
    print("=" * 120)
    print("  A-014 S4 — ONE-SHOT HOLDOUT 2025-01-01 .. 2026-05-21, decisive config USTEC-only (card section 10)")
    print("=" * 120)

    # ---- 1. the bug, both windows --------------------------------------------------------
    print("\n  [1] Inverted-geometry trades in the +1-minute column (entry on the wrong side of its stop)")
    for w in ("S3", "S4"):
        d = pd.read_csv(A / w / f"POOLED_{w}_detectability.csv")
        inv = inverted(d)
        print(f"      {w}: {inv.sum()} of {len(d)} trades, all booked as SL at a profit, sum {d.R_1x[inv].sum():+.1f}R; "
              f"pooled mean R {d.R_1x.mean():+.3f} -> {d.R_1x[~inv].mean():+.3f} without them")

    u_a = pd.read_csv(A / "S4" / "USTEC_S4_primary.csv")
    u_b = pd.read_csv(A / "S4" / "USTEC_S4_detectability.csv")
    u_b = u_b[~inverted(u_b)]

    # ---- 2. decisive config ---------------------------------------------------------------
    print("\n  [2] DECISIVE — USTEC only")
    sa1, sa2 = st(u_a.R_1x, u_a.entry_ts), st(u_a.R_2x, u_a.entry_ts)
    sb1, sb2 = st(u_b.R_1x, u_b.entry_ts), st(u_b.R_2x, u_b.entry_ts)
    line("bound A  fill at level, 1x spread", sa1)
    line("bound A  fill at level, 2x spread", sa2)
    line("bound B  +1 min fill (bug-fixed), 1x", sb1)
    line("bound B  +1 min fill (bug-fixed), 2x", sb2)

    # ---- 3. why B beats A here: the same-bar convention -----------------------------------
    sb = u_a.samebar.astype(bool)
    print("\n  [3] Why the late fill beats the at-level fill in this window")
    print(f"      at-level trades stopped INSIDE the break minute (adverse-first convention): {sb.sum()} of {len(u_a)} "
          f"({100*sb.mean():.1f}%) at {u_a.R_1x[sb].mean():+.2f}R each = {u_a.R_1x[sb].sum():+.1f}R")
    s3 = pd.read_csv(A / "S3" / "USTEC_S3_primary.csv")
    print(f"      same share in 2023-24 validation: {100*s3.samebar.astype(bool).mean():.1f}%")
    print(f"      at-level WITHOUT those minutes: mean R {u_a.R_1x[~sb].mean():+.3f} (n {int((~sb).sum())}) — the late fill "
          f"is not skipping signal, it is skipping minutes the at-level column scores as losses by assumption.")
    print("      M1 bars cannot say whether the break or the reversal came first inside that minute, so bound A is")
    print("      the conservative bound and bound B is not an upper bound either. The operative point needs M-001.")

    # ---- 4. S4 pass criterion --------------------------------------------------------------
    print("\n  [4] S4 PASS criterion (pre-registered): USTEC mean net R > 0 at 1x spread at the operative fill")
    ok_a, ok_b = sa1["meanR"] > 0, sb1["meanR"] > 0
    print(f"      bound A {sa1['meanR']:+.3f} -> {'positive' if ok_a else 'NOT positive'};  "
          f"bound B {sb1['meanR']:+.3f} -> {'positive' if ok_b else 'NOT positive'}")
    print("      bounds agree -> verdict FINAL today:" if ok_a == ok_b else "      bounds disagree -> PENDING M-001",
          "S4 PASS" if (ok_a and ok_b) else ("S4 FAIL" if (not ok_a and not ok_b) else ""))

    print("\n      Re-pricing bound A at M-001 slippage (entry moved against the trade, stop fixed):")
    print(f"      {'slip pts':>9}{'PF 1x':>9}{'meanR 1x':>10}{'PF 2x':>9}{'meanR 2x':>10}")
    for s in (0.0, 0.5, 1.0, 1.8, 3.0, 5.0):
        r1, r2 = reprice(u_a, s, "cost_1x"), reprice(u_a, s, "cost_2x")
        pf = lambda r: r[r > 0].sum() / -r[r <= 0].sum()
        print(f"      {s:>9.2f}{pf(r1):>9.3f}{r1.mean():>+10.3f}{pf(r2):>9.3f}{r2.mean():>+10.3f}")
    lo, hi = 0.0, 60.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if reprice(u_a, mid, "cost_1x").mean() > 0 else (lo, mid)
    print(f"      break-even slippage on the holdout, 1x: {lo:.2f} pts")

    # ---- 5. full acceptance bar, USTEC 2018-2026 ----------------------------------------------
    print("\n  [5] FULL ACCEPTANCE BAR — USTEC, IS (same-bar corrected) + validation + holdout, bound A")
    isb = pd.read_csv(A / "POOLED_primary_CORRECTED_samebarSL.csv")
    isb = isb[isb.instrument == "USTEC"]
    allR1 = pd.concat([pd.Series(isb.R_corr_1x.values, index=pd.to_datetime(isb.entry_ts)),
                       pd.Series(s3.R_1x.values, index=pd.to_datetime(s3.entry_ts)),
                       pd.Series(u_a.R_1x.values, index=pd.to_datetime(u_a.entry_ts))]).sort_index()
    allR2 = pd.concat([pd.Series(isb.R_corr_2x.values, index=pd.to_datetime(isb.entry_ts)),
                       pd.Series(s3.R_2x.values, index=pd.to_datetime(s3.entry_ts)),
                       pd.Series(u_a.R_2x.values, index=pd.to_datetime(u_a.entry_ts))]).sort_index()
    f1, f2 = st(allR1.values, allR1.index), st(allR2.values, allR2.index)
    line("USTEC 2018-2026, 1x", f1)
    line("USTEC 2018-2026, 2x", f2)
    eq = (1 + 0.01 * allR2).cumprod()
    dd = float((1 - eq / eq.cummax()).max() * 100)
    yrs2 = allR2.groupby(allR2.index.year).sum()
    checks = [
        (">= 400 trades", f1["n"] >= 400, f"{f1['n']}"),
        ("PF >= 1.25 at 2x spread (bound A, detectability NOT resolved)", f2["pf"] >= 1.25, f"{f2['pf']:.3f}"),
        (">= 6 of the calendar years positive at 2x", int((yrs2 > 0).sum()) >= 6,
         f"{int((yrs2 > 0).sum())}/{len(yrs2)} {dict((int(k), round(v, 1)) for k, v in yrs2.items())}"),
        ("maxDD < 20% at 1% risk/trade, 2x spread", dd < 20, f"{dd:.1f}%"),
        ("positive on the holdout, once", ok_a and ok_b, f"A {sa1['meanR']:+.3f} / B {sb1['meanR']:+.3f}"),
        ("parameter neighbourhood stable", None, "not re-run (exit brackets fail by construction, see card §8)"),
        ("demo reconciles trade-for-trade", None, "not started"),
    ]
    for lab, ok, val in checks:
        print(f"      [{'PASS' if ok else ('----' if ok is None else 'FAIL')}] {lab:<62} {val}")

    # ---- 6. descriptive only ----------------------------------------------------------------
    print("\n  [6] DESCRIPTIVE ONLY (no verdict): US30 and pooled, same window, bound A 1x")
    for inst in ("US30",):
        x = pd.read_csv(A / "S4" / f"{inst}_S4_primary.csv")
        line(f"{inst} at level, 1x", st(x.R_1x, x.entry_ts))
    p = pd.read_csv(A / "S4" / "POOLED_S4_primary.csv")
    line("POOLED at level, 1x", st(p.R_1x, p.entry_ts))

    # ---- red flags --------------------------------------------------------------------------
    m = u_a.assign(mo=pd.to_datetime(u_a.entry_ts).dt.to_period("M")).groupby("mo").R_1x.sum()
    print("\n  Red-flag scan (protocol): "
          f"PF>3 {sa1['pf'] > 3} | >0.5R/trade {sa1['meanR'] > 0.5} | every month positive {bool((m > 0).all())} | "
          f"A/B inversion {sb1['meanR'] > sa1['meanR']} (explained in [3]; bug in [1] fixed)")


if __name__ == "__main__":
    main()
