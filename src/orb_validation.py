"""
A-014 S3 — validation window 2023-01-01 .. 2024-12-31 ONLY.
Do not touch 2025+ with this script (holdout stays untouched until S4).

Reuses the audited A-014 mechanism (causal first-break-wins, EoD hold,
Amendment 3/4 guards) with Amendment 6 built in NATIVELY this time:
same-bar adverse-touch check happens inside simulate_from_entry, not as a
post-hoc correction. Two frozen configs, no tuning:
  (a) primary — unfiltered
  (b) A-014b — rel_vol >= 0.8602 (frozen IS 33.3rd pctile threshold)
"""
import numpy as np
import pandas as pd
from datetime import time as dtime
from pathlib import Path

from data import load_m1

DATA = {
    "USTEC": "USTEC.csv",
    "US30": "US30.csv",
}
OUT = Path(__file__).resolve().parent.parent / "results" / "S3"
OUT.mkdir(parents=True, exist_ok=True)

# validation window + a lookback buffer purely for ATR(14,M15) and the
# 20-day rel_vol trailing median warm-up (both causal, computed only
# forward from data <= the trade date, buffer is not a signal source)
WINDOW = "2022.11.01", "2024.12.31"
S3_START, S3_END = pd.Timestamp("2023-01-01"), pd.Timestamp("2025-01-01")
DAY_BOUNDARY = dtime(23, 0, 0)

CONVENTIONS = {"stock": (16, 15, 16, 30, 16, 45)}
ATR_PERIOD = 14
MIN_WINDOW_FRAC = 0.80
VOLNORM_LOOKBACK_DAYS = 20
REL_VOL_THRESHOLD = 0.8602  # frozen IS 33.3rd pctile, A-014b


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
                         entry_spread, sl, tp, direction, n, detect_lag=0):
    """Amendment 4: scan starts at entry_idx+1+detect_lag (0=signal-bar fill,
    1=detectability A/B +1-bar fill). Amendment 6: the FILL BAR itself is
    checked for adverse touch under adverse-first before the forward loop
    even starts -- native, not post-hoc."""
    fill_idx = entry_idx + detect_lag
    day_of_entry = trading_day(pd.Timestamp(m1_ts[fill_idx]))
    session_close_ts = pd.Timestamp(day_of_entry) + pd.Timedelta(hours=23)

    samebar = False
    h0, l0 = m1_high[fill_idx], m1_low[fill_idx]
    if direction == 1 and l0 <= sl:
        samebar = True
        return {"exit_price": sl, "exit_ts": m1_ts[fill_idx], "reason": "SL",
                "fill_idx": fill_idx, "samebar": True}, samebar
    if direction == -1 and h0 >= sl:
        samebar = True
        return {"exit_price": sl, "exit_ts": m1_ts[fill_idx], "reason": "SL",
                "fill_idx": fill_idx, "samebar": True}, samebar

    scan_start = fill_idx + 1
    prev_idx = fill_idx
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
        return None, False
    return {"exit_price": exit_price, "exit_ts": exit_ts, "reason": reason,
            "fill_idx": fill_idx, "samebar": False}, samebar


def build_trade_row(m1_ts, m1_spread, entry_idx, entry_price, entry_spread, sl, tp,
                     direction, exit_info):
    exit_price, exit_ts, reason, fill_idx = (exit_info["exit_price"], exit_info["exit_ts"],
                                              exit_info["reason"], exit_info["fill_idx"])
    raw_pnl = direction * (exit_price - entry_price)
    exit_idx = min(np.searchsorted(m1_ts, np.datetime64(exit_ts)), len(m1_ts) - 1)
    exit_spread = m1_spread[exit_idx]
    fill_spread = m1_spread[fill_idx]  # actual fill-bar spread (detectability-lag aware)
    cost_1x = fill_spread + exit_spread
    net_1x = raw_pnl - cost_1x
    cost_2x = 2 * fill_spread + 2 * exit_spread
    net_2x = raw_pnl - cost_2x
    R = abs(entry_price - sl)
    return {
        "entry_ts": pd.Timestamp(m1_ts[entry_idx]), "fill_ts": pd.Timestamp(m1_ts[fill_idx]),
        "exit_ts": pd.Timestamp(exit_ts),
        "direction": "long" if direction == 1 else "short", "entry": entry_price, "sl": sl, "tp": tp,
        "exit": exit_price, "R": R,
        "R_1x": net_1x / R if R > 0 else 0.0, "R_2x": net_2x / R if R > 0 else 0.0,
        "net_pnl_1x": net_1x, "raw_pnl": raw_pnl, "cost_1x": cost_1x, "cost_2x": cost_2x,
        "reason": reason, "samebar": exit_info["samebar"],
    }


def process_instrument(name, path):
    m1 = load_m1(path, *WINDOW)
    print(f"{name}: M1 rows {len(m1)} (load window incl. warm-up buffer)")
    atr_series = m15_atr14(m1)

    or_sh, or_sm, or_eh, or_em, permit_eh, permit_em = CONVENTIONS["stock"]
    exp_or_bars = (or_eh * 60 + or_em) - (or_sh * 60 + or_sm)
    exp_permit_bars = (permit_eh * 60 + permit_em) - (or_eh * 60 + or_em)

    m1_ts = m1["ts"].to_numpy()
    m1_open = m1["open"].to_numpy()
    m1_high = m1["high"].to_numpy()
    m1_low = m1["low"].to_numpy()
    m1_spread = m1["spread_price"].to_numpy()
    n = len(m1)

    trades_primary, trades_detect = [], []
    or_vol_history = []
    samebar_count_primary = 0
    unscanned_minutes = []

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
        mean_tickvol_or = orb["tickvol"].mean()
        recent = [v for _, v in or_vol_history[-VOLNORM_LOOKBACK_DAYS:]]
        rel_vol = mean_tickvol_or / np.median(recent) if len(recent) >= VOLNORM_LOOKBACK_DAYS else np.nan
        or_vol_history.append((day, mean_tickvol_or))

        highs = permit["high"].to_numpy()
        lows = permit["low"].to_numpy()
        opens = permit["open"].to_numpy()
        ts_arr = permit["ts"].to_numpy()
        m = len(permit)

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
        entry_ts_actual = pd.Timestamp(m1_ts[gidx])
        if not (S3_START <= entry_ts_actual < S3_END):
            continue  # window guard: only count trades whose entry falls in 2023-2024

        exit_info, samebar = simulate_from_entry(m1_ts, m1_high, m1_low, m1_open, m1_spread,
                                                   gidx, entry_price, m1_spread[gidx], sl, None,
                                                   direction, n, detect_lag=0)
        if exit_info is None:
            continue
        if samebar:
            samebar_count_primary += 1
        else:
            unscanned_minutes.append(0.0)  # scan begins at fill_idx+1, Amendment 4 satisfied

        row = build_trade_row(m1_ts, m1_spread, gidx, entry_price, m1_spread[gidx], sl, None,
                               direction, exit_info)
        row["instrument"] = name
        row["rel_vol"] = rel_vol
        trades_primary.append(row)

        # detectability A/B: +1 bar fill, same day/signal, re-simulated independently
        if gidx + 1 < n:
            entry_price_d1 = m1_open[gidx + 1]
            sl_d1 = sl
            exit_info_d1, _ = simulate_from_entry(m1_ts, m1_high, m1_low, m1_open, m1_spread,
                                                    gidx, entry_price_d1, m1_spread[gidx + 1],
                                                    sl_d1, None, direction, n, detect_lag=1)
            if exit_info_d1 is not None:
                row_d1 = build_trade_row(m1_ts, m1_spread, gidx, entry_price_d1, m1_spread[gidx + 1],
                                          sl_d1, None, direction, exit_info_d1)
                row_d1["instrument"] = name
                row_d1["rel_vol"] = rel_vol
                trades_detect.append(row_d1)

    return (pd.DataFrame(trades_primary), pd.DataFrame(trades_detect),
            samebar_count_primary, len(trades_primary))


def pf_of(r):
    wins = r[r > 0].sum(); losses = -r[r < 0].sum()
    return wins / losses if losses > 0 else np.inf


def summarize(df, col, label):
    if len(df) == 0:
        return {"label": label, "n": 0}
    r = df[col]
    yr = pd.to_datetime(df["entry_ts"]).dt.year
    by_year = r.groupby(yr).sum()
    return {
        "label": label, "n": len(df), "PF": round(pf_of(r), 3) if np.isfinite(pf_of(r)) else "inf",
        "win_rate": round((r > 0).mean(), 3), "mean_R": round(r.mean(), 4),
        "years_positive": f"{int((by_year > 0).sum())}/{by_year.shape[0]}",
        "by_year_R": {int(y): round(v, 2) for y, v in by_year.items()},
    }


if __name__ == "__main__":
    ledger = []
    all_primary, all_detect = [], []
    samebar_total, n_total = 0, 0

    for inst in ["USTEC", "US30"]:
        tp, td, sb, nt = process_instrument(inst, DATA[inst])
        tp.to_csv(OUT / f"{inst}_S3_primary.csv", index=False)
        td.to_csv(OUT / f"{inst}_S3_detectability.csv", index=False)
        all_primary.append(tp)
        all_detect.append(td)
        samebar_total += sb
        n_total += nt
        print(f"{inst}: n={nt} samebar={sb}")
        ledger.append(f"{inst}: n={nt} samebar={sb}")

    pooled = pd.concat(all_primary, ignore_index=True)
    pooled_detect = pd.concat(all_detect, ignore_index=True)
    pooled.to_csv(OUT / "POOLED_S3_primary.csv", index=False)
    pooled_detect.to_csv(OUT / "POOLED_S3_detectability.csv", index=False)

    print(f"\n=== AMENDMENT 6: same-bar adverse touches = {samebar_total}/{n_total} "
          f"({100*samebar_total/n_total:.1f}%) — native, not post-hoc ===")
    ledger.append(f"Amendment6 samebar: {samebar_total}/{n_total}")

    print("\n--- PRIMARY CONFIG (unfiltered) ---")
    for col, tag in [("R_1x", "1x spread"), ("R_2x", "2x spread")]:
        s = summarize(pooled, col, f"primary/{tag}")
        print(s)
        ledger.append(str(s))
    for inst in ["USTEC", "US30"]:
        s = summarize(pooled[pooled.instrument == inst], "R_1x", f"{inst}/primary/1x")
        print(s)
        ledger.append(str(s))

    print("\n--- DETECTABILITY A/B (+1 bar fill), primary population ---")
    for col, tag in [("R_1x", "1x spread")]:
        s = summarize(pooled_detect, col, f"detect+1bar/{tag}")
        print(s)
        ledger.append(str(s))

    print("\n--- A-014b (rel_vol >= 0.8602, frozen threshold) ---")
    filt = pooled[pooled["rel_vol"] >= REL_VOL_THRESHOLD].copy()
    filt.to_csv(OUT / "POOLED_S3_A014b_filtered.csv", index=False)
    for col, tag in [("R_1x", "1x spread"), ("R_2x", "2x spread")]:
        s = summarize(filt, col, f"A014b/{tag}")
        print(s)
        ledger.append(str(s))
    for inst in ["USTEC", "US30"]:
        s = summarize(filt[filt.instrument == inst], "R_1x", f"{inst}/A014b/1x")
        print(s)
        ledger.append(str(s))

    filt_detect = pooled_detect[pooled_detect["rel_vol"] >= REL_VOL_THRESHOLD]
    s = summarize(filt_detect, "R_1x", "A014b/detect+1bar/1x")
    print(s)
    ledger.append(str(s))
    excluded = pooled[pooled["rel_vol"] < REL_VOL_THRESHOLD]
    s = summarize(excluded, "R_1x", "A014b/EXCLUDED/1x")
    print(f"(excluded-set check) {s}")
    ledger.append(f"excluded: {s}")

    print("\n--- Amendment 2 cost sanity (both configs) ---")
    for label, df in [("primary", pooled), ("A014b", filt)]:
        gross = df["raw_pnl"].sum()
        net = (df["raw_pnl"] - df["cost_1x"]).sum()
        cost_agg = net - gross
        print(f"{label}: gross={gross:.1f} net={net:.1f} aggregate_cost={cost_agg:.1f} "
              f"({'OK negative' if cost_agg < 0 else 'BUG: costs made money'})")
        ledger.append(f"{label} cost_sanity: gross={gross:.1f} net={net:.1f} agg_cost={cost_agg:.1f}")

    print("\n--- Amendment 3 weekday distribution (primary pooled) ---")
    wd = pd.to_datetime(pooled["entry_ts"]).dt.day_name().value_counts()
    print(wd.to_dict())
    ledger.append(f"weekday: {wd.to_dict()}")

    print("\n--- exit-reason mix ---")
    print("primary:", pooled["reason"].value_counts().to_dict())
    print("A014b:", filt["reason"].value_counts().to_dict())
    ledger.append(f"exit_mix primary: {pooled['reason'].value_counts().to_dict()}")
    ledger.append(f"exit_mix A014b: {filt['reason'].value_counts().to_dict()}")

    (OUT / "S3_ledger_raw_output.txt").write_text("\n".join(str(x) for x in ledger), encoding="utf-8")
    print(f"\nSaved to {OUT}")
