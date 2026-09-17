#!/usr/bin/env python3
"""Scan for StockCharts-style RS new highs that lead price highs.

1ChartMaster's tell: the RS line often prints a new high while price is still
digesting / below its own high — then price gaps or breaks to new highs later.
This module builds that list from daily bars vs SPY without changing NEL rules.
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
class RSLeadSettings:
    benchmark: str = "SPY"
    lookback_daily: int = 252
    lookback_weekly: int = 52
    # Price must sit this far under its lookback high to count as "not yet".
    price_buffer_pct: float = 0.5
    history_period: str = "2y"
    min_bars: int = 60


def _require_yfinance():
    try:
        import yfinance as yf
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install yfinance") from error
    return yf


def _normalize_symbol(symbol: str) -> str:
    return str(symbol).strip().upper().replace(".", "-")


def download_history(symbols: list[str], settings: RSLeadSettings) -> tuple[pd.DataFrame, pd.Series]:
    """Download adjusted closes/highs for symbols + benchmark. Returns (panel, spy_close)."""
    yf = _require_yfinance()
    tickers = sorted({_normalize_symbol(s) for s in symbols if s})
    if settings.benchmark.upper() not in tickers:
        tickers.append(settings.benchmark.upper())
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
    highs = {}
    if isinstance(raw.columns, pd.MultiIndex):
        for symbol in tickers:
            if symbol not in raw.columns.get_level_values(0):
                continue
            block = raw[symbol]
            if "Close" not in block.columns or "High" not in block.columns:
                continue
            closes[symbol] = block["Close"]
            highs[symbol] = block["High"]
    else:
        # Single-ticker fallback
        symbol = tickers[0]
        closes[symbol] = raw["Close"]
        highs[symbol] = raw["High"]

    close_frame = pd.DataFrame(closes).dropna(how="all")
    high_frame = pd.DataFrame(highs).reindex(close_frame.index)
    bench = settings.benchmark.upper()
    if bench not in close_frame.columns:
        raise SystemExit(f"Benchmark {bench} history missing.")
    spy = close_frame[bench].dropna()
    return pd.concat({"close": close_frame, "high": high_frame}, axis=1), spy


def _is_new_high(series: pd.Series, lookback: int) -> bool:
    window = series.dropna().iloc[-lookback:]
    if len(window) < max(20, lookback // 4):
        return False
    latest = float(window.iloc[-1])
    peak = float(window.max())
    if not np.isfinite(latest) or not np.isfinite(peak) or peak <= 0:
        return False
    return latest >= peak * (1 - 1e-12)


def _price_at_high(close: pd.Series, high: pd.Series, lookback: int, buffer_pct: float) -> bool:
    closes = close.dropna()
    highs = high.reindex(closes.index).ffill()
    window_close = closes.iloc[-lookback:]
    window_high = highs.iloc[-lookback:]
    if len(window_close) < max(20, lookback // 4):
        return False
    latest = float(window_close.iloc[-1])
    peak = float(window_high.max())
    if not np.isfinite(latest) or not np.isfinite(peak) or peak <= 0:
        return False
    return latest >= peak * (1 - buffer_pct / 100.0)


def _weekly_frame(close: pd.Series, high: pd.Series) -> tuple[pd.Series, pd.Series]:
    frame = pd.DataFrame({"close": close, "high": high}).dropna(subset=["close"])
    weekly = frame.resample("W-FRI").agg({"close": "last", "high": "max"}).dropna()
    return weekly["close"], weekly["high"]


def score_symbol(
    symbol: str,
    close: pd.Series,
    high: pd.Series,
    spy: pd.Series,
    settings: RSLeadSettings,
    meta: dict | pd.Series | None = None,
) -> dict | None:
    aligned = pd.DataFrame({"close": close, "high": high, "spy": spy}).dropna()
    if len(aligned) < settings.min_bars:
        return None
    rs = aligned["close"] / aligned["spy"]
    rs_d = _is_new_high(rs, settings.lookback_daily)
    px_d = _price_at_high(aligned["close"], aligned["high"], settings.lookback_daily, settings.price_buffer_pct)
    w_close, w_high = _weekly_frame(aligned["close"], aligned["high"])
    w_spy, _ = _weekly_frame(aligned["spy"], aligned["spy"])
    w_rs = (w_close / w_spy).dropna()
    rs_w = _is_new_high(w_rs, settings.lookback_weekly)
    px_w = _price_at_high(w_close, w_high, settings.lookback_weekly, settings.price_buffer_pct)

    if not (rs_d or rs_w):
        return None

    lookback_high = float(aligned["high"].iloc[-settings.lookback_daily :].max())
    last_close = float(aligned["close"].iloc[-1])
    pct_below = (lookback_high - last_close) / lookback_high * 100 if lookback_high else 0.0
    lead_d = bool(rs_d and not px_d)
    lead_w = bool(rs_w and not px_w)
    if lead_d and lead_w:
        signal = "LEAD_D_W"
    elif lead_d:
        signal = "LEAD_D"
    elif lead_w:
        signal = "LEAD_W"
    elif rs_d and rs_w:
        signal = "RS_D_W"
    elif rs_d:
        signal = "RS_D"
    else:
        signal = "RS_W"

    meta_map = meta.to_dict() if isinstance(meta, pd.Series) else dict(meta or {})
    row = {
        "name": symbol,
        "close": round(last_close, 4),
        "rs": round(float(rs.iloc[-1]), 6),
        "rs_new_high_d": rs_d,
        "price_new_high_d": px_d,
        "rs_lead_d": lead_d,
        "rs_new_high_w": rs_w,
        "price_new_high_w": px_w,
        "rs_lead_w": lead_w,
        "pct_below_price_high": round(pct_below, 2),
        "lookback_price_high": round(lookback_high, 4),
        "signal": signal,
        "is_rs_lead": lead_d or lead_w,
        "tradingview_url": tradingview_url(meta_map.get("exchange"), symbol),
    }
    for key in ("description", "exchange", "industry", "Perf.1M", "Perf.3M", "Perf.6M"):
        if key in meta_map and pd.notna(meta_map[key]):
            row[key] = meta_map[key]
    return row


def scan_rs_leads(universe: pd.DataFrame, settings: RSLeadSettings | None = None) -> pd.DataFrame:
    """Return names printing RS new highs, flagged when RS leads price."""
    settings = settings or RSLeadSettings()
    if universe.empty or "name" not in universe.columns:
        return pd.DataFrame()
    meta_map = {
        _normalize_symbol(row["name"]): row
        for _, row in universe.drop_duplicates(subset=["name"]).iterrows()
    }
    symbols = list(meta_map)
    panel, spy = download_history(symbols, settings)
    rows = []
    for symbol in symbols:
        if ("close", symbol) not in panel.columns:
            continue
        close = panel[("close", symbol)]
        high = panel[("high", symbol)] if ("high", symbol) in panel.columns else close
        scored = score_symbol(symbol, close, high, spy, settings, meta_map.get(symbol))
        if scored:
            rows.append(scored)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    signal_rank = {"LEAD_D_W": 0, "LEAD_D": 1, "LEAD_W": 2, "RS_D_W": 3, "RS_D": 4, "RS_W": 5}
    frame["_rank"] = frame["signal"].map(signal_rank).fillna(9)
    frame = frame.sort_values(["_rank", "pct_below_price_high", "name"], ascending=[True, False, True]).drop(columns=["_rank"])
    return frame.reset_index(drop=True)


def write_rs_outputs(
    frame: pd.DataFrame,
    settings: RSLeadSettings,
    output_dir: Path,
    snapshot_date: date | None = None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    export_dir = output_dir / "EXPORT"
    export_dir.mkdir(exist_ok=True)
    stamp = (snapshot_date or datetime.now().date()).isoformat()
    paths: list[Path] = []
    full_path = output_dir / f"rs_new_highs_{stamp}.csv"
    frame.to_csv(full_path, index=False)
    paths.append(full_path)
    leads = frame.loc[frame["is_rs_lead"].fillna(False)].copy() if not frame.empty else frame
    lead_path = output_dir / f"rs_leads_{stamp}.csv"
    leads.to_csv(lead_path, index=False)
    paths.append(lead_path)
    if not leads.empty:
        symbol_path = export_dir / f"rs_lead_symbols_{stamp}.csv"
        leads.loc[:, ["name"]].rename(columns={"name": "symbol"}).to_csv(symbol_path, index=False)
        paths.append(symbol_path)
    settings_path = output_dir / f"rs_lead_settings_{stamp}.csv"
    pd.DataFrame(list(asdict(settings).items()), columns=["setting", "value"]).to_csv(settings_path, index=False)
    paths.append(settings_path)
    return paths


def latest_filtered_universe(output_dir: Path) -> tuple[pd.DataFrame, date | None]:
    paths = sorted(output_dir.glob("filtered_universe_*.csv"))
    if not paths:
        raise SystemExit(f"No filtered_universe_*.csv in {output_dir}")
    path = paths[-1]
    stamp = path.name.replace("filtered_universe_", "").replace(".csv", "")
    try:
        snap = date.fromisoformat(stamp)
    except ValueError:
        snap = None
    return pd.read_csv(path), snap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan for RS new highs that lead price highs.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--universe-csv", type=Path, help="Optional filtered-universe CSV. Defaults to latest in output-dir.")
    parser.add_argument("--snapshot-date", type=date.fromisoformat, help="Stamp for output filenames.")
    parser.add_argument("--lookback-daily", type=int, default=252)
    parser.add_argument("--lookback-weekly", type=int, default=52)
    parser.add_argument("--price-buffer-pct", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = RSLeadSettings(
        lookback_daily=args.lookback_daily,
        lookback_weekly=args.lookback_weekly,
        price_buffer_pct=args.price_buffer_pct,
    )
    if args.universe_csv:
        universe = pd.read_csv(args.universe_csv)
        snap = args.snapshot_date
    else:
        universe, snap = latest_filtered_universe(args.output_dir)
        snap = args.snapshot_date or snap
    frame = scan_rs_leads(universe, settings)
    paths = write_rs_outputs(frame, settings, args.output_dir, snap)
    leads = int(frame["is_rs_lead"].sum()) if not frame.empty else 0
    print(f"RS new highs: {len(frame):,} | RS leads (before price high): {leads:,}")
    print("Saved:\n" + "\n".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
