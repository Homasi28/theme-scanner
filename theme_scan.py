#!/usr/bin/env python3
"""Build a daily industry-theme snapshot from TradingView momentum leaders."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from math import ceil
from pathlib import Path
from typing import Iterable

import pandas as pd

from industry_flow_dashboard import write_dashboard


@dataclass(frozen=True)
class Settings:
    min_dollar_volume: float = 30_000_000
    min_adr_pct: float = 4.0
    min_avg_volume_10d: int = 350_000
    top_pct: float = 0.05
    earnings_days: int = 3


CORE_COLUMNS = [
    "name",
    "description",
    "exchange",
    "industry",
    "close",
    "SMA30",
    "SMA50",
    "ADRP",
    "ATRP",
    "Perf.1M",
    "Perf.3M",
    "Perf.6M",
    "average_volume_10d_calc",
    "average_volume_30d_calc",
]

# Only used to mark a ticker as reporting soon on the desk list.
EARNINGS_COLUMNS = [
    "earnings_release_next_trading_date_fq",
    "earnings_release_date",
]

SCAN_COLUMNS = CORE_COLUMNS + EARNINGS_COLUMNS
TV_EXCHANGES = {"NASDAQ": "NASDAQ", "NYSE": "NYSE", "AMEX": "AMEX"}


def fetch_universe() -> pd.DataFrame:
    """Fetch a broad US stock universe; exact liquidity filtering happens locally.

    Keeping the dollar-volume expression out of the server-side query avoids
    depending on TradingView expression support and makes the output auditable.
    Earnings columns are requested first; if TradingView rejects a field, the
    scan retries with the core columns only.
    """
    try:
        from tradingview_screener import Query, col
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install -r requirements.txt") from error

    last_error: Exception | None = None
    for columns in (SCAN_COLUMNS, CORE_COLUMNS):
        query = (
            Query()
            .set_markets("america")
            .select(*columns)
            .where(
                col("type") == "stock",
                col("exchange").isin(["NASDAQ", "NYSE", "AMEX"]),
                col("average_volume_10d_calc") > 0,
            )
            .limit(5_000)
        )
        try:
            _, frame = query.get_scanner_data()
            return frame
        except Exception as error:  # noqa: BLE001 — TradingView field names vary
            last_error = error
    raise SystemExit(f"TradingView scan failed: {last_error}") from last_error


def _require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ValueError(
            "TradingView did not return required column(s): " + ", ".join(missing)
        )


def _assign_exact_top_flags(frame: pd.DataFrame, metric: str, rank_column: str, flag_column: str, cutoff: int) -> None:
    """Assign deterministic ranks and an exact-size top group for one metric."""
    ordered = frame.sort_values([metric, "name"], ascending=[False, True], kind="stable")
    ranks = pd.Series(range(1, len(ordered) + 1), index=ordered.index, dtype="int64")
    frame[rank_column] = ranks
    frame[flag_column] = frame[rank_column] <= cutoff


def _numeric(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")


def _parse_earnings_date(value: object) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19] if "T" in text or " " in text else text[:10], fmt).date()
        except ValueError:
            continue
    parsed = pd.to_datetime(text, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed.date()


def tradingview_url(exchange: object, symbol: object) -> str:
    ticker = str(symbol or "").strip()
    venue = TV_EXCHANGES.get(str(exchange or "").strip().upper(), str(exchange or "NASDAQ").strip().upper() or "NASDAQ")
    return f"https://www.tradingview.com/chart/?symbol={venue}:{ticker}&interval=D"


def calculate_leaders(raw: pd.DataFrame, settings: Settings) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return the eligible universe and the deduplicated momentum leaders.

    Leaders are the input to every theme count, so this stays deliberately
    mechanical: liquidity and activity filters, then the top share of each
    performance ranking.
    """
    _require_columns(raw, ["name", "industry", "close", "SMA30", "SMA50", "ADRP", "ATRP", "Perf.1M", "Perf.3M", "Perf.6M", "average_volume_10d_calc", "average_volume_30d_calc"])
    df = raw.copy()
    numeric = ["close", "SMA30", "SMA50", "ADRP", "ATRP", "Perf.1M", "Perf.3M", "Perf.6M", "average_volume_10d_calc", "average_volume_30d_calc"]
    _numeric(df, numeric)

    # ADRP and ATRP are TradingView's daily 14-period percentage indicators.
    # ADRP is the activity filter; ATRP feeds the extension column, which is
    # shown for context only and no longer filters anything.
    df["dollar_volume_30d"] = df["close"] * df["average_volume_30d_calc"]
    df["average_dollar_volume_30d"] = df["SMA30"] * df["average_volume_30d_calc"]
    df["atr_extension_from_50d"] = (df["close"] - df["SMA50"]) / (
        df["SMA50"] * (df["ATRP"] / 100)
    )

    valid_industry = ~df["industry"].fillna("").str.contains("biotech", case=False, regex=False)
    valid_metrics = (df[["close", "SMA30", "SMA50", "ADRP", "ATRP"]] > 0).all(axis=1)
    has_performance = df[["Perf.1M", "Perf.3M", "Perf.6M"]].notna().all(axis=1)
    universe = df.loc[
        valid_industry
        & valid_metrics
        & has_performance
        & (df["average_dollar_volume_30d"] > settings.min_dollar_volume)
        & (df["ADRP"] > settings.min_adr_pct)
        & (df["average_volume_10d_calc"] > settings.min_avg_volume_10d)
    ].copy()

    if universe.empty:
        return universe, universe.copy()

    cutoff = max(1, ceil(len(universe) * settings.top_pct))
    _assign_exact_top_flags(universe, "Perf.1M", "perf_1m_rank", "is_top_1m", cutoff)
    _assign_exact_top_flags(universe, "Perf.3M", "perf_3m_rank", "is_top_3m", cutoff)
    _assign_exact_top_flags(universe, "Perf.6M", "perf_6m_rank", "is_top_6m", cutoff)
    universe["momentum_score"] = universe[["Perf.1M", "Perf.3M", "Perf.6M"]].mean(axis=1)

    # Combine the three leader groups. A symbol can lead in more than one
    # timeframe but appears only once in the final leader list.
    leaders = pd.concat(
        [
            universe.loc[universe["is_top_1m"]],
            universe.loc[universe["is_top_3m"]],
            universe.loc[universe["is_top_6m"]],
        ],
        ignore_index=True,
    ).drop_duplicates(subset="name", keep="first")
    sort_order = ["momentum_score", "Perf.1M", "Perf.3M", "Perf.6M"]
    leaders.sort_values(sort_order, ascending=False, inplace=True)
    return universe.sort_values("momentum_score", ascending=False), leaders


def annotate_display(frame: pd.DataFrame, settings: Settings, snapshot_date: date | None = None) -> pd.DataFrame:
    """Add the chart link and earnings flag the desk list needs."""
    result = frame.copy()
    if result.empty:
        return result
    as_of = snapshot_date or datetime.now().date()

    earnings_col = next((column for column in EARNINGS_COLUMNS if column in result.columns), None)
    if earnings_col:
        earnings = result[earnings_col].map(_parse_earnings_date)
        result["earnings_date"] = earnings.map(lambda day: day.isoformat() if day else "")
        result["earnings_soon"] = earnings.map(
            lambda day: bool(day and 0 <= (day - as_of).days <= settings.earnings_days)
        )
    else:
        result["earnings_date"] = ""
        result["earnings_soon"] = False

    result["tradingview_url"] = [
        tradingview_url(row.get("exchange"), row.get("name")) for _, row in result.iterrows()
    ]
    return result


def prepare_for_export(frame: pd.DataFrame) -> pd.DataFrame:
    """Order and round the columns so the daily snapshot stays scan-friendly."""
    preferred = [
        "name", "description", "exchange", "industry", "close", "SMA30", "SMA50", "ADRP", "ATRP",
        "average_volume_10d_calc", "average_volume_30d_calc", "dollar_volume_30d", "average_dollar_volume_30d",
        "Perf.1M", "perf_1m_rank", "Perf.3M", "perf_3m_rank", "Perf.6M", "perf_6m_rank",
        "momentum_score", "atr_extension_from_50d",
        "earnings_date", "earnings_soon", "tradingview_url",
        "is_top_1m", "is_top_3m", "is_top_6m",
    ]
    columns = [column for column in preferred if column in frame.columns]
    result = frame.loc[:, columns].copy()
    return result.round({
        "close": 2, "SMA30": 2, "SMA50": 2, "ADRP": 2, "ATRP": 2,
        "dollar_volume_30d": 0, "average_dollar_volume_30d": 0,
        "Perf.1M": 2, "Perf.3M": 2, "Perf.6M": 2, "momentum_score": 2,
        "atr_extension_from_50d": 2,
    })


def write_outputs(
    universe: pd.DataFrame,
    leaders: pd.DataFrame,
    settings: Settings,
    output_dir: Path,
    snapshot_date: date | None = None,
) -> list[Path]:
    """Write each review view as a plain CSV file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    export_dir = output_dir / "EXPORT"
    export_dir.mkdir(exist_ok=True)
    stamp = (snapshot_date or datetime.now().date()).isoformat()
    settings_frame = pd.DataFrame(list(asdict(settings).items()), columns=["setting", "value"])
    outputs = {
        "momentum_leaders": prepare_for_export(leaders),
        "filtered_universe": prepare_for_export(universe),
        "settings": settings_frame,
    }
    paths = []
    for name, frame in outputs.items():
        path = output_dir / f"{name}_{stamp}.csv"
        frame.to_csv(path, index=False)
        paths.append(path)
    symbol_path = export_dir / f"leader_symbols_{stamp}.csv"
    symbols = leaders.loc[:, ["name"]].rename(columns={"name": "symbol"}) if not leaders.empty else pd.DataFrame({"symbol": []})
    symbols.to_csv(symbol_path, index=False)
    paths.append(symbol_path)
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan industry themes from momentum leaders.")
    parser.add_argument("--min-adr-pct", type=float, default=4.0, help="Minimum TradingView ADR%% (default: 4).")
    parser.add_argument("--top-pct", type=float, default=0.05, help="Top share from each 1-, 3-, and 6-month ranking before deduplication (default: 0.05).")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"), help="CSV output directory.")
    parser.add_argument("--snapshot-date", type=date.fromisoformat, help="Date to use in output filenames (YYYY-MM-DD).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0 < args.top_pct <= 1:
        raise SystemExit("--top-pct must be greater than 0 and no more than 1.")
    if args.min_adr_pct < 0:
        raise SystemExit("--min-adr-pct cannot be negative.")
    settings = Settings(min_adr_pct=args.min_adr_pct, top_pct=args.top_pct)
    snapshot = args.snapshot_date
    raw = fetch_universe()
    universe, leaders = calculate_leaders(raw, settings)
    universe = annotate_display(universe, settings, snapshot)
    leaders = annotate_display(leaders, settings, snapshot)
    paths = write_outputs(universe, leaders, settings, args.output_dir, snapshot)
    paths.append(write_dashboard(args.output_dir))
    print(
        f"Scanned: {len(raw):,} | eligible: {len(universe):,} | leaders: {len(leaders):,}"
    )
    print("Saved:\n" + "\n".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
