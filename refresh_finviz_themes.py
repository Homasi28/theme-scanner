#!/usr/bin/env python3
"""Rebuild theme_baskets.json from Finviz's thematic classification.

Finviz tags stocks into themes editorially; there is no published formula and
no download, but each theme is queryable through the screener. This walks every
theme, pages through its constituents, and writes the ticker lists out.

Theme membership changes slowly, so this is a manual quarterly job rather than
part of the daily scan. It also needs a real browser: the screener renders its
rows client-side, so a plain HTTP fetch returns an empty table, and Finviz
blocks datacenter IPs, so it will not work from CI.

    python refresh_finviz_themes.py                 # all themes
    python refresh_finviz_themes.py --themes quantumcomputing,robotics
    python refresh_finviz_themes.py --dry-run       # report, write nothing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

BASKETS_FILE = Path(__file__).with_name("theme_baskets.json")
SCREENER = "https://finviz.com/screener.ashx?v=111&f=theme_{slug}&r={row}"
ROWS_PER_PAGE = 20
MAX_PAGES = 40  # 800 names; no Finviz theme comes close

# Finviz's theme slugs, with the display names used in the dashboard.
THEMES = {
    "agingpopulationlongevity": "Aging Population & Longevity",
    "agriculturefoodtech": "Agriculture & Food Tech",
    "artificialintelligence": "Artificial Intelligence",
    "autonomoussystems": "Autonomous Systems",
    "bigdata": "Big Data",
    "biometrics": "Biometrics",
    "cloudcomputing": "Cloud Computing",
    "commoditiesagriculture": "Commodities - Agriculture",
    "commoditiesenergy": "Commodities - Energy",
    "commoditiesmetals": "Commodities - Metals",
    "consumergoods": "Consumer Goods",
    "cryptoblockchain": "Crypto & Blockchain",
    "cybersecurity": "Cybersecurity",
    "defenseaerospace": "Defense & Aerospace",
    "digitalentertainment": "Digital Entertainment",
    "ecommerce": "E-Commerce",
    "educationtechnology": "Education Technology",
    "electricvehicles": "Electric Vehicles",
    "energyrenewable": "Energy - Renewable",
    "energytraditional": "Energy - Traditional",
    "environmentalsustainability": "Environmental Sustainability",
    "fintech": "Fintech",
    "hardware": "Hardware",
    "healthcarebiotech": "Healthcare & Biotech",
    "healthyfoodnutrition": "Healthy Food & Nutrition",
    "industrialautomation": "Industrial Automation",
    "internetofthings": "Internet of Things",
    "nanotechnology": "Nanotechnology",
    "quantumcomputing": "Quantum Computing",
    "realestatereits": "Real Estate & REITs",
    "robotics": "Robotics",
    "semiconductors": "Semiconductors",
    "smarthome": "Smart Home",
    "socialmedia": "Social Media",
    "software": "Software",
    "spacetech": "Space Tech",
    "telecommunications": "Telecommunications",
    "transportationlogistics": "Transportation & Logistics",
    "virtualaugmentedreality": "Virtual & Augmented Reality",
    "wearables": "Wearables",
}

TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,6}$")
# Every cell in a screener row links to stock?t=TICKER, so the symbol comes
# from the href rather than the cell text.
HREF_TICKER = re.compile(r"[?&]t=([A-Za-z0-9.\-]+)")
# Ads and trackers keep the page "loading" forever; skip anything cosmetic.
BLOCKED_RESOURCES = {"image", "font", "media", "stylesheet"}


def scrape_theme(page, slug: str) -> list[str]:
    """Page through one theme until Finviz stops returning new tickers."""
    known: set[str] = set()
    for index in range(MAX_PAGES):
        url = SCREENER.format(slug=slug, row=index * ROWS_PER_PAGE + 1)
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        try:
            page.wait_for_selector("table.screener_table a", timeout=20_000)
        except Exception:  # noqa: BLE001 — an empty page just ends the walk
            break
        hrefs = page.eval_on_selector_all(
            "table.screener_table a", "els => els.map(e => e.getAttribute('href') || '')"
        )
        page_tickers = []
        for href in hrefs:
            match = HREF_TICKER.search(href)
            if not match:
                continue
            symbol = match.group(1).upper()
            if TICKER.match(symbol) and symbol not in page_tickers:
                page_tickers.append(symbol)
        fresh = [t for t in page_tickers if t not in known]
        if not fresh:
            break
        known.update(fresh)
        if len(page_tickers) < ROWS_PER_PAGE:
            break
    return sorted(known)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--themes", help="Comma-separated Finviz slugs (default: all).")
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing.")
    parser.add_argument("--out", type=Path, default=BASKETS_FILE, help="Destination JSON.")
    args = parser.parse_args()

    slugs = [s.strip() for s in args.themes.split(",")] if args.themes else list(THEMES)
    unknown = [s for s in slugs if s not in THEMES]
    if unknown:
        raise SystemExit(f"Unknown theme slug(s): {', '.join(unknown)}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise SystemExit(
            "Missing dependency. Run: pip install playwright && playwright install chromium"
        ) from error

    baskets: dict[str, list[str]] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
        )
        page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in BLOCKED_RESOURCES
            else route.continue_(),
        )
        for position, slug in enumerate(slugs, start=1):
            name = THEMES[slug]
            try:
                tickers = scrape_theme(page, slug)
            except Exception as error:  # noqa: BLE001 — one bad theme should not lose the rest
                print(f"[{position}/{len(slugs)}] {name}: FAILED ({error})", file=sys.stderr)
                continue
            if tickers:
                baskets[name] = tickers
            print(f"[{position}/{len(slugs)}] {name}: {len(tickers)} tickers", flush=True)
        browser.close()

    if not baskets:
        raise SystemExit("No themes scraped; leaving the existing baskets alone.")

    print(f"\n{len(baskets)} themes, {sum(len(v) for v in baskets.values())} entries, "
          f"{len({t for v in baskets.values() for t in v})} unique tickers")
    if args.dry_run:
        print("--dry-run: nothing written.")
        return 0

    with args.out.open("w", encoding="utf-8") as handle:
        json.dump(dict(sorted(baskets.items())), handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"Wrote {args.out} on {date.today().isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
