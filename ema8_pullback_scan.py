#!/usr/bin/env python3
"""Scan Liquid Leaders for pullbacks into a rising 8-week EMA.

1ChartMaster / swing playbook: stalk strength into the rising 8-week average
instead of chasing highs. Universe is Liquid Leaders only — NEL rules unchanged.
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
class Ema8PullbackSettings:
    ema_span: int = 8
    # How many consecutive weekly EMA rises to require (2 = latest > prior).
    rising_weeks: int = 2
    # Close may sit this far above the EMA and still count as a tag/pullback.
    touch_pct: float = 3.0
    # Allow a shallow undercut of the EMA (shakeout).
    max_undercut_pct: float = 1.5
    # Must be at least this far below the recent 8-week high.
    min_off_high_pct: float = 1.0
    history_period: str = "2y"
    min_weeks: int = 20


def _require_yfinance():
    try:
        import yfinance as yf
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install yfinance") from error
    return yf


def _normalize_symbol(symbol: str) -> str:
    return str(symbol).strip().upper().replace(".", "-")


def download_ohlc(symbols: list[str], settings: Ema8PullbackSettings) -> pd.DataFrame:
    """Return MultiIndex columns (field, symbol) for close/high/low."""
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

    closes, highs, lows = {}, {}, {}
    if isinstance(raw.columns, pd.MultiIndex):
        for symbol in tickers:
            if symbol not in raw.columns.get_level_values(0):
                continue
            block = raw[symbol]
            if not {"Close", "High", "Low"}.issubset(block.columns):
                continue
            closes[symbol] = block["Close"]
            highs[symbol] = block["High"]
            lows[symbol] = block["Low"]
    else:
        symbol = tickers[0]
        closes[symbol] = raw["Close"]
        highs[symbol] = raw["High"]
        lows[symbol] = raw["Low"]

    return pd.concat(
        {
            "close": pd.DataFrame(closes),
            "high": pd.DataFrame(highs),
            "low": pd.DataFrame(lows),
        },
        axis=1,
    ).dropna(how="all")


def _ema_rising(ema: pd.Series, rising_weeks: int) -> bool:
    if len(ema) < max(3, rising_weeks + 1):
        return False
    for step in range(1, rising_weeks):
        newer = float(ema.iloc[-step])
        older = float(ema.iloc[-(step + 1)])
        if not (np.isfinite(newer) and np.isfinite(older) and newer > older):
            return False
    return True


def score_symbol(
    symbol: str,
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    settings: Ema8PullbackSettings,
    meta: dict | pd.Series | None = None,
) -> dict | None:
    frame = pd.DataFrame({"close": close, "high": high, "low": low}).dropna()
    if frame.empty:
        return None
    weekly = (
        frame.resample("W-FRI")
        .agg({"close": "last", "high": "max", "low": "min"})
        .dropna()
    )
    if len(weekly) < settings.min_weeks:
        return None

    ema = weekly["close"].ewm(span=settings.ema_span, adjust=False).mean()
    if not _ema_rising(ema, settings.rising_weeks):
        return None

    ema_now = float(ema.iloc[-1])
    last_close = float(frame["close"].iloc[-1])
    if not np.isfinite(ema_now) or ema_now <= 0 or not np.isfinite(last_close):
        return None

    dist_pct = (last_close - ema_now) / ema_now * 100.0
    if dist_pct > settings.touch_pct:
        return None
    if dist_pct < -settings.max_undercut_pct:
        return None

    recent_high = float(weekly["high"].iloc[-settings.ema_span :].max())
    off_high_pct = (recent_high - last_close) / recent_high * 100.0 if recent_high else 0.0
    if off_high_pct < settings.min_off_high_pct:
        return None

    week_low = float(weekly["low"].iloc[-1])
    tagged = week_low <= ema_now * (1 + settings.touch_pct / 100.0)
    slope_pct = (float(ema.iloc[-1]) - float(ema.iloc[-2])) / float(ema.iloc[-2]) * 100.0

    meta_map = meta.to_dict() if isinstance(meta, pd.Series) else dict(meta or {})
    row = {
        "name": symbol,
        "close": round(last_close, 4),
        "ema8w": round(ema_now, 4),
        "dist_to_ema8w_pct": round(dist_pct, 2),
        "ema8w_slope_pct": round(slope_pct, 3),
        "off_8w_high_pct": round(off_high_pct, 2),
        "tagged_ema8w": bool(tagged or abs(dist_pct) <= settings.touch_pct),
        "ema8w_rising": True,
        "signal": "EMA8W_PB",
        "tradingview_url": tradingview_url(meta_map.get("exchange"), symbol),
    }
    for key in ("description", "exchange", "industry", "Perf.1M", "Perf.3M", "Perf.6M"):
        if key in meta_map and pd.notna(meta_map[key]):
            row[key] = meta_map[key]
    return row


def scan_ema8_pullbacks(leaders: pd.DataFrame, settings: Ema8PullbackSettings | None = None) -> pd.DataFrame:
    """Return Liquid Leaders tagging a rising 8-week EMA."""
    settings = settings or Ema8PullbackSettings()
    if leaders.empty or "name" not in leaders.columns:
        return pd.DataFrame()
    meta_map = {
        _normalize_symbol(row["name"]): row
        for _, row in leaders.drop_duplicates(subset=["name"]).iterrows()
    }
    symbols = list(meta_map)
    panel = download_ohlc(symbols, settings)
    rows = []
    for symbol in symbols:
        if ("close", symbol) not in panel.columns:
            continue
        scored = score_symbol(
            symbol,
            panel[("close", symbol)],
            panel[("high", symbol)] if ("high", symbol) in panel.columns else panel[("close", symbol)],
            panel[("low", symbol)] if ("low", symbol) in panel.columns else panel[("close", symbol)],
            settings,
            meta_map.get(symbol),
        )
        if scored:
            rows.append(scored)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    # Closest to the EMA first, then strongest rising slope.
    frame["_abs"] = frame["dist_to_ema8w_pct"].abs()
    frame = frame.sort_values(["_abs", "ema8w_slope_pct", "name"], ascending=[True, False, True]).drop(columns=["_abs"])
    return frame.reset_index(drop=True)


def write_ema8_outputs(
    frame: pd.DataFrame,
    settings: Ema8PullbackSettings,
    output_dir: Path,
    snapshot_date: date | None = None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    export_dir = output_dir / "EXPORT"
    export_dir.mkdir(exist_ok=True)
    stamp = (snapshot_date or datetime.now().date()).isoformat()
    paths: list[Path] = []
    full_path = output_dir / f"ema8_pullbacks_{stamp}.csv"
    frame.to_csv(full_path, index=False)
    paths.append(full_path)
    if not frame.empty:
        symbol_path = export_dir / f"ema8_pullback_symbols_{stamp}.csv"
        frame.loc[:, ["name"]].rename(columns={"name": "symbol"}).to_csv(symbol_path, index=False)
        paths.append(symbol_path)
    settings_path = output_dir / f"ema8_pullback_settings_{stamp}.csv"
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
    parser = argparse.ArgumentParser(description="Scan Liquid Leaders for rising 8-week EMA pullbacks.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--leaders-csv", type=Path, help="Optional momentum_leaders CSV. Defaults to latest in output-dir.")
    parser.add_argument("--snapshot-date", type=date.fromisoformat, help="Stamp for output filenames.")
    parser.add_argument("--touch-pct", type=float, default=3.0)
    parser.add_argument("--max-undercut-pct", type=float, default=1.5)
    parser.add_argument("--min-off-high-pct", type=float, default=1.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = Ema8PullbackSettings(
        touch_pct=args.touch_pct,
        max_undercut_pct=args.max_undercut_pct,
        min_off_high_pct=args.min_off_high_pct,
    )
    if args.leaders_csv:
        leaders = pd.read_csv(args.leaders_csv)
        snap = args.snapshot_date
    else:
        leaders, snap = latest_momentum_leaders(args.output_dir)
        snap = args.snapshot_date or snap
    frame = scan_ema8_pullbacks(leaders, settings)
    paths = write_ema8_outputs(frame, settings, args.output_dir, snap)
    print(f"EMA8 pullbacks (from {len(leaders):,} Liquid Leaders): {len(frame):,}")
    print("Saved:\n" + "\n".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
