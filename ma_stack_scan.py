#!/usr/bin/env python3
"""Scan Liquid Leaders for 5>10 with a fresh/near 20/30 MA cross.

Setup: short stack already bullish (SMA5 > SMA10), while the medium stack
is flipping (SMA20 crossing above SMA30). Built from daily bars on LL only.
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
class MaStackSettings:
    history_period: str = "6mo"
    min_bars: int = 40
    # Treat as "crossing" when 20 is above 30 by at most this percent.
    cross_band_pct: float = 0.75
    # Count a fresh cross within this many sessions (inclusive of today).
    cross_lookback_days: int = 3


def _require_yfinance():
    try:
        import yfinance as yf
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install yfinance") from error
    return yf


def _normalize_symbol(symbol: str) -> str:
    return str(symbol).strip().upper().replace(".", "-")


def download_closes(symbols: list[str], settings: MaStackSettings) -> pd.DataFrame:
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
    closes = {}
    if isinstance(raw.columns, pd.MultiIndex):
        for symbol in tickers:
            if symbol not in raw.columns.get_level_values(0):
                continue
            block = raw[symbol]
            if "Close" not in block.columns:
                continue
            closes[symbol] = block["Close"]
    else:
        closes[tickers[0]] = raw["Close"]
    return pd.DataFrame(closes).dropna(how="all")


def _crossed_up(fast: pd.Series, slow: pd.Series, lookback: int) -> tuple[bool, int | None]:
    """Return (crossed_recently, days_ago) where days_ago=0 is today."""
    for days_ago in range(0, lookback):
        i = -1 - days_ago
        j = i - 1
        if abs(j) > len(fast) or abs(j) > len(slow):
            break
        newer_fast, newer_slow = float(fast.iloc[i]), float(slow.iloc[i])
        older_fast, older_slow = float(fast.iloc[j]), float(slow.iloc[j])
        if not all(np.isfinite(v) for v in (newer_fast, newer_slow, older_fast, older_slow)):
            continue
        if newer_fast >= newer_slow and older_fast < older_slow:
            return True, days_ago
    return False, None


def score_symbol(
    symbol: str,
    close: pd.Series,
    settings: MaStackSettings,
    meta: dict | pd.Series | None = None,
) -> dict | None:
    series = close.dropna()
    if len(series) < settings.min_bars:
        return None
    sma5 = series.rolling(5).mean()
    sma10 = series.rolling(10).mean()
    sma20 = series.rolling(20).mean()
    sma30 = series.rolling(30).mean()
    s5, s10, s20, s30 = map(float, (sma5.iloc[-1], sma10.iloc[-1], sma20.iloc[-1], sma30.iloc[-1]))
    if not all(np.isfinite(v) and v > 0 for v in (s5, s10, s20, s30)):
        return None
    if not (s5 > s10):
        return None
    if not (s20 >= s30):
        return None

    gap_pct = (s20 - s30) / s30 * 100.0
    crossed, days_ago = _crossed_up(sma20, sma30, settings.cross_lookback_days)
    crossing = gap_pct <= settings.cross_band_pct
    if not (crossed or crossing):
        return None

    if crossed and days_ago == 0:
        signal = "20x30_TODAY"
    elif crossed:
        signal = f"20x30_{days_ago}D"
    else:
        signal = "20x30_NEAR"

    meta_map = meta.to_dict() if isinstance(meta, pd.Series) else dict(meta or {})
    row = {
        "name": symbol,
        "close": round(float(series.iloc[-1]), 4),
        "SMA5": round(s5, 4),
        "SMA10": round(s10, 4),
        "SMA20": round(s20, 4),
        "SMA30": round(s30, 4),
        "sma5_gt_sma10": True,
        "sma20_gt_sma30": True,
        "sma20_30_gap_pct": round(gap_pct, 3),
        "cross_days_ago": days_ago if days_ago is not None else "",
        "signal": signal,
        "tradingview_url": tradingview_url(meta_map.get("exchange"), symbol),
    }
    for key in ("description", "exchange", "industry", "Perf.1M", "Perf.3M", "Perf.6M"):
        if key in meta_map and pd.notna(meta_map[key]):
            row[key] = meta_map[key]
    return row


def scan_ma_stack(leaders: pd.DataFrame, settings: MaStackSettings | None = None) -> pd.DataFrame:
    settings = settings or MaStackSettings()
    if leaders.empty or "name" not in leaders.columns:
        return pd.DataFrame()
    meta_map = {
        _normalize_symbol(row["name"]): row
        for _, row in leaders.drop_duplicates(subset=["name"]).iterrows()
    }
    closes = download_closes(list(meta_map), settings)
    rows = []
    for symbol in meta_map:
        if symbol not in closes.columns:
            continue
        scored = score_symbol(symbol, closes[symbol], settings, meta_map.get(symbol))
        if scored:
            rows.append(scored)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)

    def _rank(signal: object) -> int:
        text = str(signal)
        if text == "20x30_TODAY":
            return 0
        if text == "20x30_NEAR":
            return 50
        if text.startswith("20x30_") and text.endswith("D"):
            try:
                return int(text.removeprefix("20x30_").removesuffix("D"))
            except ValueError:
                return 90
        return 99

    frame["_rank"] = frame["signal"].map(_rank)
    frame = frame.sort_values(["_rank", "sma20_30_gap_pct", "name"]).drop(columns=["_rank"])
    return frame.reset_index(drop=True)


def write_ma_stack_outputs(
    frame: pd.DataFrame,
    settings: MaStackSettings,
    output_dir: Path,
    snapshot_date: date | None = None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    export_dir = output_dir / "EXPORT"
    export_dir.mkdir(exist_ok=True)
    stamp = (snapshot_date or datetime.now().date()).isoformat()
    paths: list[Path] = []
    full = output_dir / f"ma_stack_{stamp}.csv"
    frame.to_csv(full, index=False)
    paths.append(full)
    if not frame.empty:
        symbols = export_dir / f"ma_stack_symbols_{stamp}.csv"
        frame.loc[:, ["name"]].rename(columns={"name": "symbol"}).to_csv(symbols, index=False)
        paths.append(symbols)
    settings_path = output_dir / f"ma_stack_settings_{stamp}.csv"
    pd.DataFrame(list(asdict(settings).items()), columns=["setting", "value"]).to_csv(settings_path, index=False)
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
    parser = argparse.ArgumentParser(description="Scan LL for 5>10 with 20/30 cross.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--leaders-csv", type=Path)
    parser.add_argument("--snapshot-date", type=date.fromisoformat)
    parser.add_argument("--cross-band-pct", type=float, default=0.75)
    parser.add_argument("--cross-lookback-days", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = MaStackSettings(
        cross_band_pct=args.cross_band_pct,
        cross_lookback_days=args.cross_lookback_days,
    )
    if args.leaders_csv:
        leaders = pd.read_csv(args.leaders_csv)
        snap = args.snapshot_date
    else:
        leaders, snap = latest_momentum_leaders(args.output_dir)
        snap = args.snapshot_date or snap
    frame = scan_ma_stack(leaders, settings)
    paths = write_ma_stack_outputs(frame, settings, args.output_dir, snap)
    print(f"MA stack (from {len(leaders):,} Liquid Leaders): {len(frame):,}")
    print("Saved:\n" + "\n".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
