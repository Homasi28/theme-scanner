#!/usr/bin/env python3
"""Fetch Finviz's industry group performance.

TradingView's industry taxonomy splits some groups in ways that hide a move:
Lam Research and Applied Materials sit in "Industrial Machinery" next to pumps
and conveyors, so a semicap rally averages away. Finviz keeps them together in
"Semiconductor Equipment & Materials". This pulls Finviz's own group table so
the desk can rank on their taxonomy instead.

Unlike theme membership, these are daily market numbers, so this wants to run
with each scan. It needs a real browser (the table renders client-side) and a
residential IP (Finviz blocks datacenter ranges), so it works from a Mac but
not from GitHub Actions. Failure is non-fatal: the dashboard falls back to the
TradingView-derived ranking.

    python fetch_finviz_groups.py
    python fetch_finviz_groups.py --snapshot-date 2026-09-23
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

GROUPS_URL = "https://finviz.com/groups.ashx?g=industry&v=140&o=-perf1w"
BLOCKED_RESOURCES = {"image", "font", "media", "stylesheet"}
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

# Finviz column header -> dashboard window key.
WINDOWS = {
    "Perf Week": "1w",
    "Perf Month": "1m",
    "Perf Quart": "3m",
    "Perf Half": "6m",
}
SLUG = re.compile(r"f=ind_([a-z0-9]+)")


def _pct(value: str) -> float | None:
    text = (value or "").strip().replace("%", "").replace(",", "")
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fetch_groups() -> pd.DataFrame:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise SystemExit(
            "Missing dependency. Run: pip install playwright && playwright install chromium"
        ) from error

    with sync_playwright() as play:
        browser = play.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)
        page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in BLOCKED_RESOURCES
            else route.continue_(),
        )
        page.goto(GROUPS_URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_selector("table.groups_table tr", timeout=30_000)
        table = page.eval_on_selector_all(
            "table.groups_table tr",
            "rows => rows.map(r => ({"
            "  cells: Array.from(r.querySelectorAll('th,td')).map(c => c.textContent.trim()),"
            "  href: (r.querySelector('a') || {}).getAttribute"
            "         ? r.querySelector('a').getAttribute('href') : ''"
            "}))",
        )
        browser.close()

    if not table:
        raise SystemExit("Finviz returned no group rows.")
    header = table[0]["cells"]
    try:
        name_at = header.index("Name")
    except ValueError as error:
        raise SystemExit(f"Unexpected Finviz table header: {header}") from error
    window_at = {header.index(label): key for label, key in WINDOWS.items() if label in header}
    if len(window_at) != len(WINDOWS):
        missing = set(WINDOWS) - {header[i] for i in window_at}
        raise SystemExit(f"Finviz is missing expected column(s): {', '.join(sorted(missing))}")

    rows = []
    for entry in table[1:]:
        cells = entry["cells"]
        if len(cells) <= max(window_at):
            continue
        name = cells[name_at]
        if not name:
            continue
        slug_match = SLUG.search(entry.get("href") or "")
        for index, window in window_at.items():
            value = _pct(cells[index])
            if value is None:
                continue
            rows.append({
                "scope": "finviz",
                "window": window,
                "industry": name,
                "members": pd.NA,
                "median_pct": value,
                "mean_pct": value,
                "slug": slug_match.group(1) if slug_match else "",
            })
    return pd.DataFrame(rows, columns=["scope", "window", "industry", "members", "median_pct", "mean_pct", "slug"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--snapshot-date", type=date.fromisoformat, help="Output stamp (YYYY-MM-DD).")
    args = parser.parse_args()

    frame = fetch_groups()
    if frame.empty:
        raise SystemExit("No Finviz group rows parsed; leaving existing data alone.")

    stamp = (args.snapshot_date or date.today()).isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / f"finviz_groups_{stamp}.csv"
    frame.to_csv(path, index=False)

    groups = frame["industry"].nunique()
    best = frame.loc[frame["window"] == "1w"].nlargest(3, "median_pct")
    print(f"{groups} Finviz industry groups -> {path}")
    for row in best.itertuples():
        print(f"  1w leader: {row.industry} {row.median_pct:+.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
