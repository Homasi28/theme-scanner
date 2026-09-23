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
# Performance view for one industry, already ranked by the week.
MEMBERS_URL = "https://finviz.com/screener.ashx?v=141&f=ind_{slug}&o=-perf1w"
MEMBERS_PER_GROUP = 20  # one page; these are the names actually worth seeing
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
# Row links carry the clean symbol; the cell text is prefixed with the
# alphabet-index letter, which turns SNDK into SSNDK.
HREF_TICKER = re.compile(r"[?&]t=([A-Za-z0-9.\-]+)")
MEMBER_WINDOWS = {"Perf Week": "1w", "Perf Month": "1m", "Perf Quart": "3m", "Perf Half": "6m"}


def _pct(value: str) -> float | None:
    text = (value or "").strip().replace("%", "").replace(",", "")
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fetch_groups(page) -> pd.DataFrame:
    page.goto(GROUPS_URL, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_selector("table.groups_table tr", timeout=30_000)
    table = page.eval_on_selector_all(
        "table.groups_table tr",
        "rows => rows.map(r => ({"
        "  cells: Array.from(r.querySelectorAll('th,td')).map(c => c.textContent.trim()),"
        "  href: (r.querySelector('a') || {getAttribute:()=>''}).getAttribute('href')"
        "}))",
    )
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


def fetch_members(page, groups: pd.DataFrame, limit: int) -> pd.DataFrame:
    """Top names inside each group, already ranked by weekly performance."""
    targets = groups.loc[groups["slug"] != "", ["industry", "slug"]].drop_duplicates()
    rows = []
    for position, target in enumerate(targets.itertuples(), start=1):
        try:
            page.goto(MEMBERS_URL.format(slug=target.slug), wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_selector("table.screener_table tr", timeout=25_000)
            table = page.eval_on_selector_all(
                "table.screener_table tr",
                "rows => rows.map(r => ({"
                "  cells: Array.from(r.querySelectorAll('th,td')).map(c => c.textContent.trim()),"
                "  href: (r.querySelector('a[href*=\"t=\"]') || {getAttribute:()=>''}).getAttribute('href')"
                "}))",
            )
        except Exception as error:  # noqa: BLE001 — one bad group must not lose the rest
            print(f"  [{position}/{len(targets)}] {target.industry}: FAILED ({str(error)[:60]})", file=sys.stderr)
            continue
        if not table:
            continue
        header = table[0]["cells"]
        window_at = {header.index(label): key for label, key in MEMBER_WINDOWS.items() if label in header}
        if not window_at:
            continue
        rank = 0
        for entry in table[1:]:
            match = HREF_TICKER.search(entry.get("href") or "")
            if not match:
                continue
            rank += 1
            if rank > limit:
                break
            record = {"industry": target.industry, "rank": rank, "ticker": match.group(1).upper()}
            for index, window in window_at.items():
                record[window] = _pct(entry["cells"][index]) if index < len(entry["cells"]) else None
            rows.append(record)
        print(f"  [{position}/{len(targets)}] {target.industry}: {rank} names", flush=True)
    return pd.DataFrame(rows, columns=["industry", "rank", "ticker", "1w", "1m", "3m", "6m"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--snapshot-date", type=date.fromisoformat, help="Output stamp (YYYY-MM-DD).")
    parser.add_argument("--no-members", action="store_true", help="Skip the per-group name lists.")
    parser.add_argument("--members", type=int, default=MEMBERS_PER_GROUP, help="Names to keep per group.")
    args = parser.parse_args()

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
        frame = fetch_groups(page)
        members = pd.DataFrame() if args.no_members else fetch_members(page, frame, args.members)
        browser.close()

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

    if not members.empty:
        members_path = args.output_dir / f"finviz_group_members_{stamp}.csv"
        members.to_csv(members_path, index=False)
        print(f"{len(members):,} names across {members['industry'].nunique()} groups -> {members_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
