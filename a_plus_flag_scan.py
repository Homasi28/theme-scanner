#!/usr/bin/env python3
"""Scan Liquid Leaders for A++ Flag setups — prefer BEFORE the breakout.

Primary job: stalk coils under the pivot (NVDA / MU / SNDK / INTC / TSLA playbook).
Day-0 pivot breaks are secondary. Late continuation (e.g. ASST weeks after Aug 19)
is rejected.

1. Prior thrust (flagpole) — strong multi-week advance into the base
2. Flag coil — multi-week sideways / mild pullback with volatility contraction
3. MA stack — rising 20MA (orange) / 50MA (green); 50 holds; 20/50 pinch into break
4. Flat / descending pivot — resistance = flag high; coil sits just under it
5. Volume dry-up in the coil; RVOL expansion only required on day-0 break
6. Anti-chase — not already extended above the 20MA; breakouts only on day 0
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from focus_list import tradingview_url


@dataclass(frozen=True)
class APlusFlagSettings:
    history_period: str = "2y"
    min_bars: int = 130
    sma_fast: int = 20
    sma_slow: int = 50
    # Flagpole: min % advance over this many sessions before the flag window
    thrust_lookback: int = 50
    min_thrust_pct: float = 18.0
    # Flag length (trading days) — multi-week coil like the A++ examples
    flag_min_days: int = 20
    flag_max_days: int = 75
    # Flag depth from local peak (NVDA ~22%; allow up to ~35%)
    max_flag_depth_pct: float = 35.0
    # Volatility contraction: flag high-low range vs prior equal window
    max_range_ratio: float = 0.90
    # Hold the 50MA: median distance of flag closes vs SMA50 (pct)
    # Negative = below; allow shallow undercuts
    min_median_vs_sma50_pct: float = -3.0
    # SMA20 and SMA50 pinch into the break (gap as % of price)
    max_ma_pinch_pct: float = 10.0
    # Breakouts: day-of only (find before / as it breaks — not days later)
    breakout_lookback_days: int = 1
    # Volume
    vol_sma: int = 20
    max_flag_vol_ratio: float = 0.95
    min_breakout_rvol: float = 1.15
    # Anti-chase: breakout day range vs ATR
    atr_period: int = 14
    max_break_day_atr_mult: float = 2.0
    # How close to pivot counts as "coiling" (within pct of flag high)
    coil_near_pivot_pct: float = 6.0
    # Reject runners already extended above the 20MA (ASST post Aug-19)
    max_dist_above_sma20_pct: float = 10.0
    # Reject if already through the pivot by more than this (continuation)
    max_overshoot_pct: float = 2.5


def _require_yfinance():
    try:
        import yfinance as yf
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install yfinance") from error
    return yf


def _normalize_symbol(symbol: str) -> str:
    return str(symbol).strip().upper().replace(".", "-")


def download_ohlcv(symbols: list[str], settings: APlusFlagSettings) -> pd.DataFrame:
    """MultiIndex columns (field, symbol) for OHLC + volume."""
    yf = _require_yfinance()
    tickers = sorted({_normalize_symbol(s) for s in symbols if s})
    if not tickers:
        return pd.DataFrame()
    raw = yf.download(
        tickers=tickers,
        period=settings.history_period,
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="ticker",
    )
    if raw.empty:
        raise SystemExit("No price history returned from yfinance.")

    fields = {"Close": "close", "High": "high", "Low": "low", "Volume": "volume"}
    blocks: dict[str, dict[str, pd.Series]] = {v: {} for v in fields.values()}
    if isinstance(raw.columns, pd.MultiIndex):
        for symbol in tickers:
            if symbol not in raw.columns.get_level_values(0):
                continue
            block = raw[symbol]
            for src, dest in fields.items():
                if src in block.columns:
                    blocks[dest][symbol] = block[src]
    else:
        symbol = tickers[0]
        for src, dest in fields.items():
            if src in raw.columns:
                blocks[dest][symbol] = raw[src]

    return pd.concat({k: pd.DataFrame(v) for k, v in blocks.items() if v}, axis=1).dropna(how="all")


def _sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev).abs(), (low - prev).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(period).mean()


def _macd_hist(close: pd.Series) -> pd.Series:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd - signal


def _best_flag_window(
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    settings: APlusFlagSettings,
) -> tuple[int, dict] | None:
    """Flag = consolidation AFTER the thrust peak (excludes today's bar)."""
    n = len(close)
    # Search peak in the pre-today window (leave room for min flag + thrust lookback)
    search_end = n - 2  # yesterday
    search_start = max(settings.thrust_lookback, n - 2 - settings.flag_max_days - 5)
    if search_end - search_start < settings.flag_min_days:
        return None

    # Peak = highest high in the lookback that still leaves a long enough coil after it
    best: tuple[int, dict] | None = None
    for peak_i in range(search_start, search_end - settings.flag_min_days + 1):
        # Peak must be a local thrust top: close near the high of a run-up
        peak_high = float(high.iloc[peak_i])
        if not np.isfinite(peak_high) or peak_high <= 0:
            continue
        # Prefer peaks that are within 3% of the max high from peak_i back thrust_lookback
        run_slice = slice(max(0, peak_i - settings.thrust_lookback), peak_i + 1)
        run_max = float(high.iloc[run_slice].max())
        if peak_high < run_max * 0.97:
            continue

        flag_start = peak_i + 1
        flag_end = n - 1  # exclusive end at today → coil through yesterday
        flag_len = flag_end - flag_start
        if flag_len < settings.flag_min_days or flag_len > settings.flag_max_days:
            continue

        coil = slice(flag_start, flag_end)
        flag_high = float(high.iloc[coil].max())
        flag_low = float(low.iloc[coil].min())
        if not (np.isfinite(flag_high) and np.isfinite(flag_low) and flag_high > flag_low > 0):
            continue
        # Coil ceiling should not be a new leg — stay near / under the peak
        if flag_high > peak_high * 1.02:
            continue

        flag_range = flag_high - flag_low
        prior = slice(max(0, flag_start - flag_len), flag_start)
        if high.iloc[prior].size < max(10, flag_len // 2):
            continue
        prior_high = float(high.iloc[prior].max())
        prior_low = float(low.iloc[prior].min())
        if not (np.isfinite(prior_high) and np.isfinite(prior_low) and prior_high > prior_low):
            continue
        prior_range = prior_high - prior_low
        range_ratio = flag_range / prior_range if prior_range > 0 else 9.0
        if range_ratio > settings.max_range_ratio:
            continue

        depth_pct = (peak_high - flag_low) / peak_high * 100.0
        if depth_pct > settings.max_flag_depth_pct:
            continue

        thrust_base_i = max(0, peak_i - settings.thrust_lookback)
        thrust_base = float(close.iloc[thrust_base_i])
        thrust_top = float(close.iloc[peak_i])
        if thrust_base <= 0 or not np.isfinite(thrust_base):
            continue
        thrust_pct = (thrust_top - thrust_base) / thrust_base * 100.0
        if thrust_pct < settings.min_thrust_pct:
            continue

        metrics = {
            "flag_len": flag_len,
            "flag_high": max(flag_high, peak_high),  # pivot = peak / coil ceiling
            "flag_low": flag_low,
            "flag_depth_pct": depth_pct,
            "range_ratio": range_ratio,
            "thrust_pct": thrust_pct,
            "peak_i": peak_i,
        }
        # Prefer longer, tighter coils with stronger thrust
        score = flag_len * (1.0 - range_ratio) + thrust_pct * 0.05
        if best is None or score > best[0]:
            best = (score, metrics)
    return best


def score_symbol(
    symbol: str,
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    volume: pd.Series,
    settings: APlusFlagSettings,
    meta: dict | pd.Series | None = None,
) -> dict | None:
    frame = pd.DataFrame(
        {"close": close, "high": high, "low": low, "volume": volume}
    ).dropna()
    if len(frame) < settings.min_bars:
        return None

    c = frame["close"]
    h = frame["high"]
    l = frame["low"]
    v = frame["volume"]
    sma20 = _sma(c, settings.sma_fast)
    sma50 = _sma(c, settings.sma_slow)
    atr = _atr(h, l, c, settings.atr_period)
    vol_ma = v.rolling(settings.vol_sma).mean()
    macd_h = _macd_hist(c)

    last = float(c.iloc[-1])
    s20 = float(sma20.iloc[-1])
    s50 = float(sma50.iloc[-1])
    s20_prev = float(sma20.iloc[-5]) if len(sma20) >= 5 else s20
    s50_prev = float(sma50.iloc[-5]) if len(sma50) >= 5 else s50
    if not all(np.isfinite(x) for x in (last, s20, s50, s20_prev, s50_prev)):
        return None

    # Rising / non-falling 50MA (allow flat coil); 20 rising or price near it
    sma20_rising = s20 > s20_prev
    sma50_rising = s50 >= s50_prev * 0.997
    if len(sma50) >= 21:
        sma50_rising = sma50_rising or s50 > float(sma50.iloc[-21])
    above_50 = last >= s50 * (1 + settings.min_median_vs_sma50_pct / 100.0)
    stack_ok = above_50 and sma50_rising and (last >= s20 * 0.97 or sma20_rising)
    if not stack_ok:
        return None

    # Anti-chase: already riding far above the 20MA = late (ASST after Aug 19)
    dist_above_sma20_pct = (last - s20) / s20 * 100.0
    if dist_above_sma20_pct > settings.max_dist_above_sma20_pct:
        return None

    picked = _best_flag_window(c, h, l, settings)
    if picked is None:
        return None
    _, flag = picked
    flag_len = int(flag["flag_len"])
    flag_high = float(flag["flag_high"])
    flag_low = float(flag["flag_low"])

    # 50MA support during coil
    coil_closes = c.iloc[-(flag_len + 1) : -1]
    coil_sma50 = sma50.iloc[-(flag_len + 1) : -1]
    vs_50 = ((coil_closes - coil_sma50) / coil_sma50 * 100.0).replace([np.inf, -np.inf], np.nan).dropna()
    if vs_50.empty:
        return None
    median_vs_50 = float(vs_50.median())
    if median_vs_50 < settings.min_median_vs_sma50_pct:
        return None

    ma_pinch_pct = abs(s20 - s50) / last * 100.0
    pinched = ma_pinch_pct <= settings.max_ma_pinch_pct

    # Volume dry-up: coil avg vs prior equal window (thrust), not late-vs-early inside flag
    coil_vol = v.iloc[-(flag_len + 1) : -1]
    prior_vol = v.iloc[-(2 * flag_len + 1) : -(flag_len + 1)]
    coil_vol_avg = float(coil_vol.mean()) if len(coil_vol) else 0.0
    prior_vol_avg = float(prior_vol.mean()) if len(prior_vol) else coil_vol_avg
    vol_ratio = coil_vol_avg / prior_vol_avg if prior_vol_avg > 0 else 1.0
    vol_dry = vol_ratio <= settings.max_flag_vol_ratio

    # Pivot distance: positive = still under resistance (stalk zone)
    dist_to_pivot_pct = (flag_high - last) / flag_high * 100.0
    overshoot_pct = -dist_to_pivot_pct if dist_to_pivot_pct < 0 else 0.0
    broke = last > flag_high

    # Day-0 break only: first close through pivot today
    break_days_ago: int | None = None
    if broke and len(c) >= 2:
        pivot_yest = float(h.iloc[-(flag_len + 1) : -1].max())
        close_yest = float(c.iloc[-2])
        if last > pivot_yest and close_yest <= pivot_yest:
            break_days_ago = 0
        elif last > flag_high and close_yest <= flag_high:
            break_days_ago = 0

    vol_now = float(v.iloc[-1])
    vol_base = float(vol_ma.iloc[-1]) if np.isfinite(vol_ma.iloc[-1]) else 0.0
    rvol = vol_now / vol_base if vol_base > 0 else 0.0
    atr_now = float(atr.iloc[-1]) if np.isfinite(atr.iloc[-1]) else 0.0
    day_range = float(h.iloc[-1] - l.iloc[-1])
    day_atr_mult = day_range / atr_now if atr_now > 0 else 9.0
    macd_now = float(macd_h.iloc[-1]) if np.isfinite(macd_h.iloc[-1]) else 0.0
    macd_prev = float(macd_h.iloc[-3]) if len(macd_h) >= 3 and np.isfinite(macd_h.iloc[-3]) else macd_now
    macd_turning = macd_now > macd_prev and macd_now > 0

    # Primary: coil under pivot with dry volume + MA pinch (find BEFORE breakout)
    near_pivot = (
        not broke
        and 0.0 <= dist_to_pivot_pct <= settings.coil_near_pivot_pct
    )
    is_coil = near_pivot and vol_dry and pinched

    # Secondary: day-0 break only, not already overshot / chased
    is_breakout = (
        broke
        and break_days_ago == 0
        and overshoot_pct <= settings.max_overshoot_pct
        and rvol >= settings.min_breakout_rvol
        and day_atr_mult <= settings.max_break_day_atr_mult
        and vol_dry
        and pinched
    )

    if not is_coil and not is_breakout:
        return None

    # Grade checklist
    checks = {
        "thrust": flag["thrust_pct"] >= settings.min_thrust_pct,
        "contraction": flag["range_ratio"] <= settings.max_range_ratio,
        "depth_ok": flag["flag_depth_pct"] <= settings.max_flag_depth_pct,
        "sma50_hold": median_vs_50 >= settings.min_median_vs_sma50_pct,
        "sma_rising": sma20_rising and sma50_rising,
        "pinch": pinched,
        "vol_dry": vol_dry,
        "near_20": dist_above_sma20_pct <= settings.max_dist_above_sma20_pct,
        "macd": macd_turning or macd_now > 0,
    }
    if is_breakout:
        checks["rvol"] = rvol >= settings.min_breakout_rvol
        checks["not_chased"] = day_atr_mult <= settings.max_break_day_atr_mult
    passed = sum(1 for ok in checks.values() if ok)
    total = len(checks)
    if passed >= total - 1:
        grade = "A++"
    elif passed >= total - 2:
        grade = "A+"
    else:
        grade = "A"

    # Prefer stalk label; day-0 break is secondary
    signal = "APLUS_COIL" if is_coil else "APLUS_BREAKOUT"
    meta_map = meta.to_dict() if isinstance(meta, pd.Series) else dict(meta or {})
    row = {
        "name": symbol,
        "signal": signal,
        "grade": grade,
        "close": round(last, 4),
        "sma20": round(s20, 4),
        "sma50": round(s50, 4),
        "flag_len": flag_len,
        "flag_high": round(flag_high, 4),
        "flag_low": round(flag_low, 4),
        "flag_depth_pct": round(float(flag["flag_depth_pct"]), 2),
        "thrust_pct": round(float(flag["thrust_pct"]), 2),
        "range_ratio": round(float(flag["range_ratio"]), 3),
        "median_vs_sma50_pct": round(median_vs_50, 2),
        "ma_pinch_pct": round(ma_pinch_pct, 2),
        "dist_to_pivot_pct": round(dist_to_pivot_pct, 2),
        "dist_above_sma20_pct": round(dist_above_sma20_pct, 2),
        "break_days_ago": break_days_ago if break_days_ago is not None else "",
        "rvol": round(rvol, 2),
        "vol_dry_ratio": round(vol_ratio, 3),
        "day_atr_mult": round(day_atr_mult, 2),
        "macd_hist": round(macd_now, 4),
        "macd_turning_up": bool(macd_turning),
        "checks_passed": f"{passed}/{total}",
        "tradingview_url": tradingview_url(meta_map.get("exchange"), symbol),
    }
    for key in ("description", "exchange", "industry", "Perf.1M", "Perf.3M", "Perf.6M"):
        if key in meta_map and pd.notna(meta_map[key]):
            row[key] = meta_map[key]
    return row


def scan_a_plus_flags(leaders: pd.DataFrame, settings: APlusFlagSettings | None = None) -> pd.DataFrame:
    settings = settings or APlusFlagSettings()
    if leaders.empty or "name" not in leaders.columns:
        return pd.DataFrame()
    meta_map = {
        _normalize_symbol(row["name"]): row
        for _, row in leaders.drop_duplicates(subset=["name"]).iterrows()
    }
    symbols = list(meta_map)
    panel = download_ohlcv(symbols, settings)
    rows = []
    for symbol in symbols:
        if ("close", symbol) not in panel.columns:
            continue
        scored = score_symbol(
            symbol,
            panel[("close", symbol)],
            panel[("high", symbol)] if ("high", symbol) in panel.columns else panel[("close", symbol)],
            panel[("low", symbol)] if ("low", symbol) in panel.columns else panel[("close", symbol)],
            panel[("volume", symbol)] if ("volume", symbol) in panel.columns else pd.Series(1.0, index=panel.index),
            settings,
            meta_map.get(symbol),
        )
        if scored:
            rows.append(scored)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    grade_rank = {"A++": 0, "A+": 1, "A": 2}
    # Coils first (pre-breakout stalk), then day-0 breaks
    frame["_g"] = frame["grade"].map(grade_rank).fillna(9)
    frame["_sig"] = frame["signal"].map({"APLUS_COIL": 0, "APLUS_BREAKOUT": 1}).fillna(9)
    frame = frame.sort_values(
        ["_sig", "_g", "dist_to_pivot_pct", "name"],
        ascending=[True, True, True, True],
    ).drop(columns=["_g", "_sig"])
    return frame.reset_index(drop=True)


def write_a_plus_flag_outputs(
    frame: pd.DataFrame,
    settings: APlusFlagSettings,
    output_dir: Path,
    snapshot_date: date | None = None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    export_dir = output_dir / "EXPORT"
    export_dir.mkdir(exist_ok=True)
    stamp = (snapshot_date or datetime.now().date()).isoformat()
    paths: list[Path] = []
    full_path = output_dir / f"a_plus_flags_{stamp}.csv"
    if frame.empty:
        cols = [
            "name",
            "signal",
            "grade",
            "close",
            "sma20",
            "sma50",
            "flag_len",
            "flag_high",
            "flag_low",
            "flag_depth_pct",
            "thrust_pct",
            "range_ratio",
            "median_vs_sma50_pct",
            "ma_pinch_pct",
            "dist_to_pivot_pct",
            "dist_above_sma20_pct",
            "break_days_ago",
            "rvol",
            "vol_dry_ratio",
            "day_atr_mult",
            "macd_hist",
            "macd_turning_up",
            "checks_passed",
            "tradingview_url",
        ]
        pd.DataFrame(columns=cols).to_csv(full_path, index=False)
    else:
        frame.to_csv(full_path, index=False)
    paths.append(full_path)
    if not frame.empty:
        breakouts = frame.loc[frame["signal"] == "APLUS_BREAKOUT"]
        coils = frame.loc[frame["signal"] == "APLUS_COIL"]
        if not breakouts.empty:
            p = export_dir / f"a_plus_flag_breakout_symbols_{stamp}.csv"
            breakouts.loc[:, ["name"]].rename(columns={"name": "symbol"}).to_csv(p, index=False)
            paths.append(p)
        if not coils.empty:
            p = export_dir / f"a_plus_flag_coil_symbols_{stamp}.csv"
            coils.loc[:, ["name"]].rename(columns={"name": "symbol"}).to_csv(p, index=False)
            paths.append(p)
        p = export_dir / f"a_plus_flag_symbols_{stamp}.csv"
        frame.loc[:, ["name"]].rename(columns={"name": "symbol"}).to_csv(p, index=False)
        paths.append(p)
    settings_path = output_dir / f"a_plus_flag_settings_{stamp}.csv"
    pd.DataFrame(list(asdict(settings).items()), columns=["setting", "value"]).to_csv(
        settings_path, index=False
    )
    paths.append(settings_path)
    return paths


def latest_momentum_leaders(output_dir: Path) -> tuple[pd.DataFrame, date | None]:
    paths = sorted(output_dir.glob("momentum_leaders_*.csv"))
    if not paths:
        raise SystemExit(f"No momentum_leaders_*.csv in {output_dir}")
    path = paths[-1]
    stamp = path.name.replace("momentum_leaders_", "").replace(".csv", "")
    try:
        snap = date.fromisoformat(stamp)
    except ValueError:
        snap = None
    return pd.read_csv(path), snap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan Liquid Leaders for A++ Flag Breakouts.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--leaders-csv", type=Path)
    parser.add_argument("--snapshot-date", type=date.fromisoformat)
    parser.add_argument("--min-thrust-pct", type=float, default=18.0)
    parser.add_argument("--flag-min-days", type=int, default=15)
    parser.add_argument("--flag-max-days", type=int, default=70)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = APlusFlagSettings(
        min_thrust_pct=args.min_thrust_pct,
        flag_min_days=args.flag_min_days,
        flag_max_days=args.flag_max_days,
    )
    if args.leaders_csv:
        leaders = pd.read_csv(args.leaders_csv)
        snap = args.snapshot_date
    else:
        leaders, snap = latest_momentum_leaders(args.output_dir)
        snap = args.snapshot_date or snap
    frame = scan_a_plus_flags(leaders, settings)
    paths = write_a_plus_flag_outputs(frame, settings, args.output_dir, snap)
    n_bo = int((frame["signal"] == "APLUS_BREAKOUT").sum()) if not frame.empty else 0
    n_coil = int((frame["signal"] == "APLUS_COIL").sum()) if not frame.empty else 0
    print(f"A++ flags (from {len(leaders):,} Liquid Leaders): {len(frame):,} (breakouts {n_bo}, coils {n_coil})")
    print("Saved:\n" + "\n".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
