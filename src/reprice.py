"""
M-001 DECISION TABLE — computed BEFORE any fill is measured.

Re-prices the A-014 S3 (validation 2023-24) trades at a grid of assumed entry slippage.
Pure arithmetic on an existing blotter: entry moves against the trade by s points, the stop
stays at the opposite opening-range extreme, the exit price is unchanged (a worse entry cannot
turn a stop-out into a survivor, and the session-close exit is a fixed price).

    R_net(s) = ((exit - entry')*sgn - cost) / |entry' - sl|      entry' = entry + s*sgn

The measured mean slippage from M-001 is looked up in this table; the verdict is whatever the
row says. No re-fitting, no re-running.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd

S3 = Path(__file__).resolve().parent.parent / "results" / "S3"
GRID = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 1.8, 2.0, 2.5, 3.0, 3.2, 4.0, 5.0]


def reprice(d, s, cost_col):
    sgn = np.where(d.direction == "long", 1.0, -1.0)
    entry = d.entry.to_numpy(float) + s * sgn
    risk = np.abs(entry - d.sl.to_numpy(float))
    R = ((d.exit.to_numpy(float) - entry) * sgn - d[cost_col].to_numpy(float)) / risk
    return R


def row(R):
    w, l = R[R > 0], R[R <= 0]
    return dict(n=len(R), pf=w.sum() / -l.sum(), meanR=R.mean(),
                t=R.mean() / (R.std(ddof=1) / np.sqrt(len(R))))


def main():
    d = pd.read_csv(S3 / "POOLED_S3_primary.csv")
    u = d[d.instrument == "USTEC"]
    # sanity: at s=0 the re-priced series must reproduce the stored R_1x
    chk = np.abs(reprice(d, 0.0, "cost_1x") - d.R_1x.to_numpy(float)).max()
    print(f"  reproduction check at s=0: max |diff| vs stored R_1x = {chk:.2e}")
    print(f"  validation 2023-24, n={len(d)} pooled / {len(u)} USTEC\n")
    print(f"  {'slip':>5} | {'POOLED 1x':>22} | {'POOLED 2x':>10} | {'USTEC 1x':>22} | {'USTEC 2x':>10}")
    print(f"  {'pts':>5} | {'PF':>6}{'meanR':>8}{'t':>8} | {'PF':>10} | {'PF':>6}{'meanR':>8}{'t':>8} | {'PF':>10}")
    print("  " + "-" * 92)
    for s in GRID:
        p1, p2 = row(reprice(d, s, "cost_1x")), row(reprice(d, s, "cost_2x"))
        u1, u2 = row(reprice(u, s, "cost_1x")), row(reprice(u, s, "cost_2x"))
        mark = ""
        if s == 0.6:
            mark = "  <- card: at or below this, fills are near-level"
        if s == 1.8:
            mark = "  <- card: above this, the kill is confirmed"
        print(f"  {s:>5.2f} | {p1['pf']:>6.3f}{p1['meanR']:>+8.3f}{p1['t']:>8.2f} | {p2['pf']:>10.3f} | "
              f"{u1['pf']:>6.3f}{u1['meanR']:>+8.3f}{u1['t']:>8.2f} | {u2['pf']:>10.3f}{mark}")
    # the two break-evens that decide it
    for lab, dd, col in (("POOLED 1x", d, "cost_1x"), ("USTEC 1x", u, "cost_1x"),
                         ("USTEC 2x", u, "cost_2x")):
        lo, hi = 0.0, 40.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if reprice(dd, mid, col).mean() > 0:
                lo = mid
            else:
                hi = mid
        print(f"  break-even slippage, {lab}: {lo:.2f} pts")
    print("\n  For reference, the 1-minute-delay column measured 3.20 pts mean / 2.10 median.")
    print("  The acceptance bar for a new card is PF >= 1.25 at 2x spread.")


if __name__ == "__main__":
    main()
