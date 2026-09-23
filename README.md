# Theme Scanner

A post-close scanner that answers one question: **which industries are gaining leadership right now?**

Every run pulls a broad US equity universe from TradingView, reduces it to liquid momentum leaders, counts those leaders by industry across three timeframes, and compares today's counts against the previous snapshot to flag themes that are expanding. Output is plain CSV plus a self-contained HTML dashboard.

Chart review is still required. A rising theme is a place to look, not a trade.

## Two ways to read a theme

The desk measures leadership two different ways, because they answer different questions.

**Magnitude — how did the industry do?** Every scanned stock is grouped by industry and the group's performance is summarised, the way a group screener does it. This ranks *all* industries, including ones holding no standout name, so a broad quiet grind higher is still visible. Median is the headline number: one +280% stock would otherwise carry a whole industry on the mean.

This comes in three scopes, switchable on the dashboard:

| Scope | Source | Why |
| --- | --- | --- |
| **Finviz groups** | Finviz's published group table | Their taxonomy keeps thematic groups whole |
| **All stocks** | every scanned stock, by TradingView industry | Always available, no scraping |
| **Liquid only** | just the names passing the filters | Removes microcap noise |

Finviz is preferred when present because TradingView's taxonomy splits groups in ways that hide a move. Lam Research and Applied Materials sit in **Industrial Machinery** next to pumps and conveyors, so a semicap rally averages away to +1.8%; Finviz keeps those names together in "Semiconductor Equipment & Materials" and shows +11.9%. Selecting a Finviz group opens its constituents on Finviz, since those members come from their classification rather than ours.

**Breadth — how many standout names does it hold?** The original signal. The universe is cut to momentum leaders, those leaders are counted by industry, and the counts are compared against the previous snapshot. Breadth is what produces the `RISING` / `KICKOFF` alerts.

An industry can top one view and be absent from the other, which is the point of having both.

## How the numbers are built

1. **Universe** — US common stocks on NASDAQ, NYSE, and AMEX passing all of:
   - 30-day average dollar volume above $30M
   - 14-period ADR% above 4%
   - 10-day average volume above 350K shares
   - industry does not contain "Biotech"
2. **Momentum leaders** — the top 5% of that universe by TradingView performance over each of 1 week, 1 month, 3 months, and 6 months, combined and deduplicated. The weekly window only adds leaders; it is deliberately left out of `momentum_score` so the ranking does not swing on a single week.
3. **Industry performance** — member performance aggregated per industry, at two scopes: `all` (every scanned stock, ~120 industries) and `liquid` (only names passing the filters above). An industry needs at least 3 members to be ranked.
4. **Industry counts** — leaders grouped by industry, per window. Counts come from the full leader file, so no narrower filter can distort the signal.
5. **Rising themes** — each snapshot is compared to the prior one:
   - `KICKOFF` — a new or thin theme reaching real breadth
   - `RISING` — an already-present theme adding names

   A theme needs at least 2 current leaders and a gain of at least 1 to be flagged. Related industries also roll up into a cluster (currently "Semis complex") so a semiconductor move is not missed when leadership spreads across peripherals and equipment names.

## Theme baskets

Industries come from exchange taxonomy, which has no label for "Quantum Computing" or "Space Tech". `theme_baskets.json` holds 40 named themes, each an explicit ticker list, imported from Finviz's thematic classification. Baskets are counted and compared exactly like industries and can raise the same `RISING` / `KICKOFF` flags, but they are tracked separately so a curated list can never distort the taxonomy counts.

A stock can sit in several themes at once, which is the point: today `INTC` lands in Artificial Intelligence, Semiconductors, Hardware, Quantum Computing, and more. Industries cannot express that.

### Refreshing the baskets

```bash
python refresh_finviz_themes.py            # all 40 themes
python refresh_finviz_themes.py --dry-run  # report counts, write nothing
```

Theme membership is editorial and changes slowly, so this is a **manual job worth running about quarterly**, not part of the daily scan. Two constraints make that the only sensible cadence:

- The Finviz screener renders its rows client-side, so the importer drives a real browser (`pip install playwright && playwright install chromium`).
- Finviz blocks datacenter IPs, so this **will not work from GitHub Actions**. Run it from your own machine.

The script never destroys existing baskets on failure: if nothing scrapes, it exits and leaves the file alone. Edit `theme_baskets.json` by hand to add your own basket; the scanner reads whatever is in it, and the next import will overwrite it.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Daily run

```bash
python theme_scan.py
```

Useful flags: `--top-pct` changes the share taken from each performance ranking (`--top-pct 0.02` for the top 2%), `--min-adr-pct` changes the activity filter, and `--snapshot-date YYYY-MM-DD` overrides the output stamp.

## Outputs

In `outputs/`:

- `finviz_groups_<date>.csv` — Finviz's 144 industry groups and their published performance, when a local run fetched it
- `industry_performance_<date>.csv` — every TradingView industry ranked by member performance, both scopes, all four windows
- `momentum_leaders_<date>.csv` — the leader list every theme count is built from
- `filtered_universe_<date>.csv` — every name passing the liquidity, ADR%, and industry filters; also the source for the dashboard drill-down
- `rising_themes_<date>.csv` — the flagged themes, with prior and current counts
- `theme_baskets_<date>.csv` — leader count per named basket, per window
- `settings_<date>.csv` — the exact rules used for that run

In `outputs/EXPORT/` (one-column ticker lists):

- `rising_theme_symbols_<date>.csv` — leaders sitting in a rising 1-month theme
- `leader_symbols_<date>.csv` — every momentum leader

Keep the prior daily CSVs. Rising-theme detection is a day-over-day comparison, and the dashboard's trend chart reads every `momentum_leaders_*.csv` in the folder, so history is what makes both work.

## Dashboard

Each run regenerates `industry_flow_dashboard.html` and an identical `index.html` for GitHub Pages. Open either in a browser. It has no build step and no runtime dependency beyond one CDN script for PNG export.

- **F1 Themes** — industries ranked by performance across the 1-week, 1-month, 3-month, and 6-month windows, with a trend chart per window and a "Do not miss" banner when breadth is expanding. Toggle between **All stocks** and **Liquid only**, and select any industry to see the eligible names inside it.
- **F2 LL** — the full leader table per window, with leading-theme names boxed and rising-theme names dashed
- **F3 Quote** — a daily Livermore line from *Reminiscences of a Stock Operator* (1923, public domain)

Below the ranking, **Theme Baskets** shows the same breadth count for the named ticker themes.

Per-symbol notes are saved in the browser's local storage. Ticker symbols open TradingView daily charts in a new tab.

## Automation

Finviz group performance is fetched separately, because it needs a browser and a residential IP:

```bash
python fetch_finviz_groups.py
```

`scripts/run_after_close.py` runs it automatically before each local scan, and treats failure as non-fatal — the dashboard simply falls back to the TradingView ranking. **A GitHub Actions run will not have it**, so the Finviz scope only appears on days the scan ran from your Mac.

**GitHub Actions** — `.github/workflows/daily-scan.yml` runs after the US close, commits the refreshed CSVs and dashboard, and needs no secrets beyond the default `GITHUB_TOKEN`. For Pages, enable it on the `main` branch with `/ (root)` as the source; the dashboard's canonical URL is set to `https://homasi28.github.io/theme-scanner/`, so update the meta tags in `industry_flow_dashboard.py` if you publish somewhere else.

**macOS launchd** — `scripts/run_after_close.py` runs the scanner once after 4:10 PM New York time on regular market days. It uses New York time for close and holiday checks, stamps output with the **next** NYSE session date (Friday post-close stamps Monday), catches up if the Mac wakes later, handles daylight-saving changes, and logs to `logs/daily_scan_<date>.log`. `scripts/com.theme-scanner.daily-scan.plist` is a template — replace the placeholder paths before loading it.

## Tests

```bash
pip install pytest
python -m pytest
```

## Notes on the data

TradingView returns `ADRP` (ADR%) and `ATRP` (ATR%) as separate percentage fields. ADR% is the activity filter. ATR% feeds the `atr_extension_from_50d` column, `(Price − SMA50) / (SMA50 × ATR%)`, which is shown in the leader table for context and does not filter anything.
