"""
A-014: Opening-range breakout CONTINUATION, USTEC + US30 (primary, stock
convention) + XAUUSD (diagnostic, forex convention).
IS 2018-01-01 .. 2022-12-31 ONLY. Do not touch 2023+ data with this script.

Event-driven, one-setup-per-day-per-instrument (Amendment 4 immune class).
Windows identical to A-013 for population comparability (inherited, not
searched). Causal first-break-wins (the A-013 fix, filed on A-013's card):
direction is decided at the FIRST touch of either OR extreme within the
permit window; a later touch of the other side is just the SL/whipsaw
playing out, never a retrospective void.
"""
import numpy as np
import pandas as pd
from datetime import time as dtime
from pathlib import Path

from data import load_m1

DATA = {
    "USTEC": "USTEC.csv",
    "US30": "US30.csv",
    "XAUUSD": "XAUUSD.csv",
}
OUT = Path(__file__).resolve().parent.parent / "results"
OUT.mkdir(parents=True, exist_ok=True)

WINDOW = "2018.01.01", "2022.12.31"
DAY_BOUNDARY = dtime(23, 0, 0)

CONVENTIONS = {
    "stock": (16, 15, 16, 30, 16, 45),  # OR_start, OR_end, permit_end (server h,m pairs)
    "forex": (15, 15, 15, 30, 15, 45),
}
ATR_PERIOD = 14
MIN_WINDOW_FRAC = 0.80
VOLNORM_LOOKBACK_DAYS = 20


def trading_day(ts):
    d = ts.normalize()
    day = d if ts.time() < DAY_BOUNDARY else d + pd.Timedelta(days=1)
    if day.weekday() == 6:
        day = day + pd.Timedelta(days=1)
    return day




def m15_atr14(m1):
    s = m1.set_index("ts")
    m15 = s[["high", "low", "close"]].resample("15min", label="left", closed="left").agg(
        high=("high", "max"), low=("low", "min"), close=("close", "last")).dropna()
    tr = pd.concat([m15["high"] - m15["low"],
                     (m15["high"] - m15["close"].shift(1)).abs(),
                     (m15["low"] - m15["close"].shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(ATR_PERIOD, min_periods=ATR_PERIOD).mean()
    atr.index = atr.index + pd.Timedelta(minutes=15)
    return atr


def atr_at(atr_series, ts):
    idx = atr_series.index.searchsorted(ts, side="right") - 1
    return atr_series.iloc[idx] if idx >= 0 else np.nan


def simulate_from_entry(m1_ts, m1_high, m1_low, m1_open, m1_spread, entry_idx, entry_price,
                         entry_spread, sl, tp, direction, n):
    """direction=1 long, -1 short. tp=None -> EoD-hold primary (SL only,
    forced flat at session close). Amendment 4: scan starts at entry_idx+1,
    zero unscanned exposure."""
    day_of_entry = trading_day(pd.Timestamp(m1_ts[entry_idx]))
    session_close_ts = pd.Timestamp(day_of_entry) + pd.Timedelta(hours=23)

    scan_start = entry_idx + 1
    prev_idx = entry_idx
    exit_price = exit_ts = reason = None
    for k in range(scan_start, n):
        bar_ts = pd.Timestamp(m1_ts[k])
        gap = bar_ts - pd.Timestamp(m1_ts[prev_idx])
        if bar_ts >= session_close_ts or gap > pd.Timedelta(minutes=90):
            exit_price, exit_ts, reason = m1_open[prev_idx], m1_ts[prev_idx], "session_close"
            break
        h, l = m1_high[k], m1_low[k]
        if direction == 1:
            sl_hit = l <= sl
            tp_hit = (tp is not None) and (h >= tp)
        else:
            sl_hit = h >= sl
            tp_hit = (tp is not None) and (l <= tp)
        if sl_hit:
            exit_price, exit_ts, reason = sl, m1_ts[k], "SL"
            break
        if tp_hit:
            exit_price, exit_ts, reason = tp, m1_ts[k], "TP"
            break
        prev_idx = k
    if exit_price is None:
        return None

    raw_pnl = direction * (exit_price - entry_price)
    exit_idx = min(np.searchsorted(m1_ts, np.datetime64(exit_ts)), n - 1)
    exit_spread = m1_spread[exit_idx]
    cost = entry_spread + exit_spread
    net = raw_pnl - cost
    R = abs(entry_price - sl)
    return {
        "entry_ts": pd.Timestamp(m1_ts[entry_idx]), "exit_ts": pd.Timestamp(exit_ts),
        "direction": "long" if direction == 1 else "short", "entry": entry_price, "sl": sl, "tp": tp,
        "exit": exit_price, "R": R, "R_result": net / R if R > 0 else 0.0, "net_pnl": net,
        "raw_pnl": raw_pnl, "cost": cost, "reason": reason,
    }


def process_instrument(name, path, convention, tp_r_mult=None):
    m1 = load_m1(path, *WINDOW)
    print(f"{name}: M1 rows {len(m1)}")
    atr_series = m15_atr14(m1)

    or_sh, or_sm, or_eh, or_em, permit_eh, permit_em = CONVENTIONS[convention]
    exp_or_bars = (or_eh * 60 + or_em) - (or_sh * 60 + or_sm)
    exp_permit_bars = (permit_eh * 60 + permit_em) - (or_eh * 60 + or_em)

    m1_ts = m1["ts"].to_numpy()
    m1_open = m1["open"].to_numpy()
    m1_high = m1["high"].to_numpy()
    m1_low = m1["low"].to_numpy()
    m1_spread = m1["spread_price"].to_numpy()
    n = len(m1)

    trades = []
    placebo_source = []
    or_vol_history = []  # (day, mean_tickvol_in_OR) for the relative-volume diagnostic

    for day, g in m1.groupby("day"):
        g = g.sort_values("ts")
        or_start = day + pd.Timedelta(hours=or_sh, minutes=or_sm)
        or_end = day + pd.Timedelta(hours=or_eh, minutes=or_em)
        permit_end = day + pd.Timedelta(hours=permit_eh, minutes=permit_em)

        orb = g[(g["ts"] >= or_start) & (g["ts"] < or_end)]
        permit = g[(g["ts"] >= or_end) & (g["ts"] < permit_end)].sort_values("ts")
        if len(orb) < MIN_WINDOW_FRAC * exp_or_bars or len(permit) < MIN_WINDOW_FRAC * exp_permit_bars:
            continue

        OR_H, OR_L = orb["high"].max(), orb["low"].min()
        or_range = OR_H - OR_L
        mean_tickvol_or = orb["tickvol"].mean()

        # relative-volume tercile input: trailing 20-day median of OR mean tickvol (causal)
        recent = [v for _, v in or_vol_history[-VOLNORM_LOOKBACK_DAYS:]]
        rel_vol = mean_tickvol_or / np.median(recent) if len(recent) >= VOLNORM_LOOKBACK_DAYS else np.nan
        or_vol_history.append((day, mean_tickvol_or))

        highs = permit["high"].to_numpy()
        lows = permit["low"].to_numpy()
        opens = permit["open"].to_numpy()
        ts_arr = permit["ts"].to_numpy()
        m = len(permit)

        # causal first-break-wins: single forward pass, first touch of EITHER side decides
        break_pos, direction = None, None
        for i in range(m):
            if highs[i] > OR_H:
                break_pos, direction = i, 1
                break
            if lows[i] < OR_L:
                break_pos, direction = i, -1
                break
        if break_pos is None:
            continue

        entry_price = max(OR_H, opens[break_pos]) if direction == 1 else min(OR_L, opens[break_pos])
        sl = OR_L if direction == 1 else OR_H
        R = abs(entry_price - sl)
        atr_val = atr_at(atr_series, ts_arr[break_pos])
        if np.isnan(atr_val) or atr_val <= 0 or not (0.3 * atr_val <= R <= 3 * atr_val):
            continue

        gidx = np.searchsorted(m1_ts, np.datetime64(ts_arr[break_pos]))
        if gidx >= n:
            continue
        tp = entry_price + direction * tp_r_mult * R if tp_r_mult is not None else None
        t = simulate_from_entry(m1_ts, m1_high, m1_low, m1_open, m1_spread, gidx, entry_price,
                                 m1_spread[gidx], sl, tp, direction, n)
        if t is None:
            continue
        t["instrument"] = name
        t["or_range"] = or_range
        t["rel_vol"] = rel_vol
        t["break_minute"] = (ts_arr[break_pos] - (day + pd.Timedelta(hours=or_eh, minutes=or_em))) / np.timedelta64(1, "m")
        trades.append(t)
        placebo_source.append((gidx, entry_price, m1_spread[gidx], R, direction, tp_r_mult))

    return pd.DataFrame(trades), placebo_source, m1_ts, m1_high, m1_low, m1_open, m1_spread, n


def summarize(trades, label):
    if len(trades) == 0:
        return {"label": label, "n": 0}
    r = trades["R_result"]
    wins = r[r > 0].sum(); losses = -r[r < 0].sum()
    pf = wins / losses if losses > 0 else np.inf
    trades = trades.copy()
    trades["year"] = pd.to_datetime(trades["entry_ts"]).dt.year
    by_year = trades.groupby("year")["R_result"].sum()
    return {
        "label": label, "n": len(trades),
        "PF": round(pf, 3) if np.isfinite(pf) else "inf",
        "win_rate": round((r > 0).mean(), 3),
        "mean_R": round(r.mean(), 4), "total_R": round(r.sum(), 2),
        "years_positive": f"{int((by_year > 0).sum())}/{by_year.shape[0]}",
        "by_year_R": {int(y): round(v, 2) for y, v in by_year.items()},
    }


def pf_of(r):
    wins = r[r > 0].sum(); losses = -r[r < 0].sum()
    return wins / losses if losses > 0 else np.inf


if __name__ == "__main__":
    ledger = []
    all_trades = []
    placebo_sources_by_inst = {}
    m1_arrays_by_inst = {}
    per_inst_summary = {}

    for inst in ["USTEC", "US30"]:
        t, psrc, m1_ts, m1_h, m1_l, m1_o, m1_sp, n = process_instrument(inst, DATA[inst], "stock", tp_r_mult=None)
        t.to_csv(OUT / f"{inst}_primary_EoDhold.csv", index=False)
        all_trades.append(t)
        placebo_sources_by_inst[inst] = psrc
        m1_arrays_by_inst[inst] = (m1_ts, m1_h, m1_l, m1_o, m1_sp, n)
        s = summarize(t, f"{inst}/primary")
        per_inst_summary[inst] = s
        print(f"{inst}: {s}")

    pooled = pd.concat(all_trades, ignore_index=True)
    pooled.to_csv(OUT / "POOLED_primary_EoDhold.csv", index=False)
    s_pooled = summarize(pooled, "POOLED primary (EoD hold)")
    print(f"\nPOOLED PRIMARY: {s_pooled}")
    both_positive = all(
        isinstance(per_inst_summary[i]["PF"], float) and per_inst_summary[i]["PF"] > 1.0 for i in per_inst_summary
    )
    print(f"both instruments individually PF>1: {both_positive}")

    if len(pooled) > 0:
        mean_R = pooled["R"].mean(); mean_cost = pooled["cost"].mean()
        print(f"\ncost sanity: mean R={mean_R:.2f} | mean cost={mean_cost:.3f} | cost/R={mean_cost/mean_R:.4f}")
        wd = pd.to_datetime(pooled["entry_ts"]).dt.day_name().value_counts()
        print(f"Amendment 3 (entry weekday): {wd.to_dict()}")
        print(f"direction split: {pooled['direction'].value_counts().to_dict()}")
        print(f"mean OR range: {pooled['or_range'].mean():.2f} | mean break-minute (post-09:30): {pooled['break_minute'].mean():.1f}")

        # diagnostics
        relvol = pooled.dropna(subset=["rel_vol"])
        if len(relvol) > 30:
            relvol = relvol.copy()
            relvol["rv_tercile"] = pd.qcut(relvol["rel_vol"], 3, labels=["low", "mid", "high"])
            print("\nrelative-volume tercile diagnostic (Zarattini 'in play' proxy, never selected on):")
            for t_ in ["low", "mid", "high"]:
                sub = relvol[relvol["rv_tercile"] == t_]
                print(f"  {t_}: n={len(sub)} PF={pf_of(sub['R_result']):.3f} mean_R={sub['R_result'].mean():.4f}")

        or_q = pd.qcut(pooled["or_range"], 4, labels=["q1", "q2", "q3", "q4"])
        print("\nOR-size quartile diagnostic:")
        for q in ["q1", "q2", "q3", "q4"]:
            sub = pooled[or_q == q]
            print(f"  {q}: n={len(sub)} PF={pf_of(sub['R_result']):.3f}")

        print("\nbreak-side split:")
        for d in ["long", "short"]:
            sub = pooled[pooled["direction"] == d]
            print(f"  {d}: n={len(sub)} PF={pf_of(sub['R_result']):.3f}")

    ledger.append(f"USTEC: {per_inst_summary['USTEC']}")
    ledger.append(f"US30: {per_inst_summary['US30']}")
    ledger.append(f"POOLED: {s_pooled} | both_instruments_PF>1={both_positive}")

    # XAU diagnostic (forex convention)
    t_xau, _, _, _, _, _, _, _ = process_instrument("XAUUSD", DATA["XAUUSD"], "forex", tp_r_mult=None)
    t_xau.to_csv(OUT / "XAUUSD_diagnostic_forexconv.csv", index=False)
    s_xau = summarize(t_xau, "XAU forex-convention diagnostic")
    print(f"\nXAU DIAGNOSTIC (forex convention, NOT pooled): {s_xau}")
    ledger.append(f"XAU diagnostic: {s_xau}")

    # neighborhood: 2R and 1.5R brackets (robustness, not primary)
    for tp_mult, tag in [(2.0, "2R_bracket"), (1.5, "1.5R_bracket")]:
        nb_trades = []
        for inst in ["USTEC", "US30"]:
            t, _, _, _, _, _, _, _ = process_instrument(inst, DATA[inst], "stock", tp_r_mult=tp_mult)
            nb_trades.append(t)
        nb_pooled = pd.concat(nb_trades, ignore_index=True)
        nb_pooled.to_csv(OUT / f"POOLED_{tag}.csv", index=False)
        s_nb = summarize(nb_pooled, tag)
        print(f"\nNEIGHBORHOOD {tag}: {s_nb}")
        ledger.append(f"{tag}: {s_nb}")

    # Amendment 5: distributional placebo -- direction-shuffled, 500 seeds, on the PRIMARY (EoD hold)
    n_seeds = 500
    print(f"\nRunning Amendment-5 direction-shuffled placebo ({n_seeds} seeds) on primary (EoD hold)...")
    all_sources = []
    for inst, psrc in placebo_sources_by_inst.items():
        for (gidx, entry_px, sp, R, direction, tpm) in psrc:
            all_sources.append((inst, gidx, entry_px, sp, R, direction))

    placebo_pfs = []
    for seed in range(n_seeds):
        rng = np.random.default_rng(seed)
        flips = rng.random(len(all_sources)) < 0.5
        rows = []
        for (inst, gidx, entry_px, sp, R, direction), flip in zip(all_sources, flips):
            d = -direction if flip else direction
            sl = entry_px - d * R
            m1_ts, m1_h, m1_l, m1_o, m1_sp, n = m1_arrays_by_inst[inst]
            t = simulate_from_entry(m1_ts, m1_h, m1_l, m1_o, m1_sp, gidx, entry_px, sp, sl, None, d, n)
            if t is not None:
                rows.append(t["R_result"])
        if rows:
            placebo_pfs.append(pf_of(pd.Series(rows)))
    placebo_pfs = np.array(placebo_pfs)
    finite = placebo_pfs[np.isfinite(placebo_pfs)]
    real_pf = s_pooled["PF"]
    pctile = (finite < real_pf).mean() * 100 if isinstance(real_pf, (int, float)) else None
    print(f"placebo distribution: n_valid={len(finite)} median={np.median(finite):.3f} "
          f"p75={np.percentile(finite,75):.3f} p95={np.percentile(finite,95):.3f}")
    print(f"REAL primary pooled PF={real_pf} -> percentile = {pctile}% "
          f"({'PASSES >=95th' if pctile and pctile>=95 else 'does NOT clear 95th'})")
    ledger.append(f"Placebo: median={np.median(finite):.3f} p95={np.percentile(finite,95):.3f} "
                   f"real_pf={real_pf} percentile={pctile}")

    (OUT / "S1_ledger_raw_output.txt").write_text("\n".join(ledger), encoding="utf-8")
    print(f"\nSaved trade CSVs and ledger to {OUT}")
