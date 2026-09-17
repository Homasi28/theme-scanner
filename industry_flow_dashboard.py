"""Generate a self-contained interactive industry-leadership dashboard."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


TIMEFRAMES = {
    "1m": "is_top_1m",
    "3m": "is_top_3m",
    "6m": "is_top_6m",
}

RECORD_COLUMNS = [
    "name",
    "industry",
    "exchange",
    "Perf.1M",
    "Perf.3M",
    "Perf.6M",
    "average_dollar_volume_30d",
    "dollar_volume_30d",
    "atr_extension_from_50d",
    "is_top_1m",
    "is_top_3m",
    "is_top_6m",
    "rvol",
    "lod_atr_pct",
    "sma20_distance_pct",
    "above_sma200",
    "earnings_soon",
    "earnings_date",
    "hard_rule_passes",
    "hard_rule_fails",
    "focus_score",
    "tradingview_url",
    "ma_aligned",
    "range_tight",
    "lod_ok",
    "ema_aligned",
    "near_ema",
    "adr_tight",
    "bb_tight",
    "plan_tight",
    "tightness_flags",
    "rvol_expand",
]


def _records_from_frame(frame: pd.DataFrame) -> list[dict]:
    columns = [column for column in RECORD_COLUMNS if column in frame.columns]
    if "name" not in columns:
        return []
    return json.loads(frame.loc[:, columns].to_json(orient="records"))


def _records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return _records_from_frame(pd.read_csv(path))


def collect_industry_history(output_dir: Path) -> list[dict]:
    """Summarise every dated momentum-leader snapshot by industry and timeframe."""
    snapshots = []
    for path in sorted(output_dir.glob("momentum_leaders_*.csv")):
        match = re.search(r"(\d{4}-\d{2}-\d{2})\.csv$", path.name)
        if not match:
            continue
        frame = pd.read_csv(path)
        if "industry" not in frame.columns:
            continue
        groups = {}
        for label, flag in TIMEFRAMES.items():
            if flag not in frame.columns:
                continue
            counts = (
                frame.loc[frame[flag].fillna(False).astype(bool), "industry"]
                .fillna("Unclassified")
                .value_counts()
                .to_dict()
            )
            groups[label] = {str(industry): int(count) for industry, count in counts.items()}
        stamp = match.group(1)
        # `groups` comes only from full momentum-leader files. The NEL subset
        # below is a display table and cannot influence theme leadership.
        snapshots.append({
            "date": stamp,
            "groups": groups,
            "liquid": _records_from_frame(frame),
            "nel": _records(output_dir / f"non_extended_leaders_{stamp}.csv"),
            "focus": _records(output_dir / f"focus_candidates_{stamp}.csv"),
        })
    return snapshots


def write_dashboard(output_dir: Path) -> Path:
    """Write an offline-friendly interactive dashboard with embedded history."""
    history = collect_industry_history(output_dir)
    dashboard = Path("industry_flow_dashboard.html")
    pages_entrypoint = Path("index.html")
    payload = json.dumps(history, separators=(",", ":"))
    template = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LLD &lt;GO&gt; | Liquid Leadership</title>
  <meta name="description" content="Find non-extended leaders from the market’s most liquid momentum stocks.">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="https://toi-sh.github.io/liquid-leadership/">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Liquid Leadership">
  <meta property="og:title" content="LLD <GO> | Liquid Leadership">
  <meta property="og:description" content="Find non-extended leaders from the market’s most liquid momentum stocks.">
  <meta property="og:url" content="https://toi-sh.github.io/liquid-leadership/">
  <meta property="og:image" content="https://toi-sh.github.io/liquid-leadership/assets/nel-social-preview.png">
  <meta property="og:image:width" content="1731">
  <meta property="og:image:height" content="909">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="LLD <GO> | Liquid Leadership">
  <meta name="twitter:description" content="Find non-extended leaders from the market’s most liquid momentum stocks.">
  <meta name="twitter:image" content="https://toi-sh.github.io/liquid-leadership/assets/nel-social-preview.png">
  <link rel="icon" type="image/png" href="assets/nel-favicon.png">
  <link rel="apple-touch-icon" href="assets/nel-favicon.png">
  <link rel="preload" href="assets/fonts/ibm-plex-mono-latin-400.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="tokens.css">
  <style>
html { color-scheme: dark; }
html, body { overflow-x: clip; }
* { box-sizing: border-box; }
html { background: var(--color-paper); }
body {
  margin: 0;
  background: var(--color-paper);
  color: var(--color-ink-2);
  font-family: var(--font-body);
  font-weight: 400;
  font-size: var(--text-base);
  line-height: 1.35;
}
img, svg, table { max-width: 100%; }
h1, h2, h3 {
  font-family: var(--font-display);
  font-style: normal;
  font-weight: 400;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-accent);
  overflow-wrap: anywhere;
  min-width: 0;
  line-height: 1;
  scroll-margin-top: calc(var(--banner-height) + var(--space-xs));
}
#hard-rules { scroll-margin-top: var(--banner-height); }
a { color: inherit; }
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
.skip-link {
  position: absolute;
  left: var(--space-sm);
  top: var(--space-sm);
  z-index: var(--z-sticky-nav);
  padding: var(--space-xs) var(--space-sm);
  background: var(--color-accent);
  color: var(--color-accent-ink);
  font-family: var(--font-display);
  text-decoration: none;
  transform: translateY(-200%);
  white-space: nowrap;
}
.skip-link:focus-visible { transform: none; outline: 2px solid var(--color-focus); outline-offset: var(--space-3xs); }

.chamfer {
  clip-path: polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px);
}

.nav-edge {
  position: sticky;
  top: 0;
  z-index: var(--z-sticky-nav);
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  gap: var(--space-sm);
  min-height: var(--banner-height);
  padding: 0 var(--page-gutter);
  background: var(--grey-800);
  color: var(--grey-100);
  border-bottom: var(--rule) solid var(--grey-100);
}
.wordmark,
.bbg-product {
  font-family: var(--font-display);
  font-style: normal;
  font-weight: 400;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--grey-100);
  text-decoration: none;
  line-height: 1;
  white-space: nowrap;
}
.wordmark { font-size: var(--text-md); color: var(--cyan-300); }
.bbg-brand {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
.bbg-product {
  font-size: var(--text-xs);
  color: var(--grey-500);
}
.bbg-keys {
  display: flex;
  flex: 1;
  min-width: 0;
  align-items: center;
  gap: var(--space-8);
  overflow-x: auto;
}
.bbg-keys a {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: 0 var(--space-8);
  min-height: 45px;
  font-family: var(--font-display);
  font-size: var(--text-xs);
  font-weight: 400;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  text-decoration: none;
  color: var(--grey-100);
  white-space: nowrap;
  flex: 0 0 auto;
  border-top: var(--rule) solid var(--grey-100);
  border-bottom: var(--rule) solid var(--grey-100);
}
.bbg-keys kbd {
  font-family: var(--font-mono);
  font-size: 0.625rem;
  font-weight: 400;
  padding: 0 0.2rem;
  border: var(--rule) solid var(--cyan-300);
  color: var(--cyan-300);
}
.nav-edge__controls {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-width: 0;
}
.bbg-clock {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 400;
  color: var(--grey-400);
  white-space: nowrap;
}
select,
.btn,
.note-input {
  border: var(--rule) solid var(--grey-100);
  border-radius: 0;
  background: transparent;
  color: var(--grey-100);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 400;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  line-height: 1;
  outline: 2px solid transparent;
  outline-offset: 1px;
}
select,
.btn {
  min-height: 45px;
  padding: 0 var(--space-16);
  white-space: nowrap;
}
select { width: 9.5rem; max-width: 100%; min-width: 0; background: var(--grey-800); }
.btn { cursor: pointer; clip-path: polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px); }
.btn--primary {
  background: var(--grey-100);
  color: var(--grey-800);
  border-color: var(--grey-100);
}
.btn--ghost {
  background: transparent;
  color: var(--grey-100);
  border-color: var(--grey-100);
}
@media (hover: hover) and (pointer: fine) {
  select:hover, .btn:hover, .note-input:hover { border-color: var(--cyan-300); color: var(--cyan-300); }
  .btn--primary:hover { background: var(--grey-200); color: var(--grey-800); border-color: var(--grey-200); }
  .ticker-link:hover { color: var(--cyan-300); text-decoration: underline; text-underline-offset: var(--space-3xs); }
  .bbg-keys a:hover { color: var(--cyan-300); border-color: var(--cyan-300); }
}
select:focus-visible,
.btn:focus-visible,
.note-input:focus-visible,
.ticker-link:focus-visible,
.wordmark:focus-visible,
.bbg-keys a:focus-visible {
  outline: 2px solid var(--color-ink);
  outline-offset: 1px;
}
select:active, .btn:active { transform: translateY(1px); }
.btn:disabled, select:disabled, .note-input:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.btn[data-state="loading"] { cursor: wait; opacity: 0.7; }
.btn[data-state="error"], .note-input[aria-invalid="true"] { border-color: var(--color-danger); color: var(--color-danger); }
.btn[data-state="success"] { border-color: var(--color-up); }

main {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0 var(--page-gutter) var(--space-lg);
}
.lede {
  display: flex;
  justify-content: space-between;
  gap: var(--space-sm);
  max-width: none;
  margin: 0 calc(var(--page-gutter) * -1) var(--space-sm);
  padding: var(--space-2xs) var(--page-gutter);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-accent);
  background: var(--color-paper-2);
  border-bottom: var(--rule) solid var(--color-rule);
}
.desk-block {
  margin-top: var(--space-md);
  border: var(--rule) solid var(--grey-100);
  padding: var(--space-xs);
  background: var(--grey-800);
  clip-path: polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px);
}
.desk-block--graphite {
  margin-inline: 0;
  padding: var(--space-xs);
  background: var(--grey-700);
  color: var(--color-ink);
  border-color: var(--cyan-300);
}
.desk-block--graphite h1,
.desk-block--graphite h2,
.desk-block--graphite h3 { color: var(--color-accent); }
.desk-block--graphite .btn--ghost {
  background: transparent;
  color: var(--color-accent);
  border-color: var(--color-accent);
}
.section-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-2xs);
  align-items: center;
  margin: 0 0 var(--space-xs);
  padding: var(--space-2xs) var(--space-xs);
  background: var(--color-paper-3);
  border-bottom: var(--rule) solid var(--color-rule);
}
.section-heading h1,
.section-heading h2 {
  margin: 0;
  font-size: var(--text-display);
  font-style: normal;
}
.section-heading .btn { justify-self: start; }
.rules {
  border: var(--rule) solid var(--grey-100);
  padding: var(--space-xs);
  margin-top: var(--space-sm);
  clip-path: polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px);
}
.rules__title {
  margin: 0 0 var(--space-xs);
  font-size: var(--text-sm);
  padding: var(--space-2xs) var(--space-xs);
  background: var(--color-paper-3);
}
.rules__groups {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-sm);
}
.rules__groups h3 {
  margin: 0 0 var(--space-2xs);
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  line-height: 1.08;
  color: var(--color-muted);
}
.rules__list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.rules__list li {
  display: grid;
  grid-template-columns: 1.25rem minmax(0, 1fr);
  gap: var(--space-2xs);
  padding-block: var(--space-3xs);
  border-top: var(--rule) solid var(--color-rule);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}
.rules__n {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--color-accent);
}
.window-sections {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-sm);
  align-items: start;
}
.panel,
.nel-window {
  min-width: 0;
  padding: 0;
  border: var(--rule) solid var(--grey-100);
  background: var(--grey-800);
}
.panel h2,
.nel-window h3 {
  margin: 0;
  padding: var(--space-2xs) var(--space-xs);
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  background: var(--color-paper-3);
}
.trend-label { margin-top: 0; border-top: var(--rule) solid var(--color-rule); }
.panel[data-frame="1m"] h2, .nel-window[data-frame="1m"] h3 { color: var(--color-frame-1m); }
.panel[data-frame="3m"] h2, .nel-window[data-frame="3m"] h3 { color: var(--color-frame-3m); }
.panel[data-frame="6m"] h2, .nel-window[data-frame="6m"] h3 { color: var(--color-frame-6m); }
.desk-block--graphite .panel,
.desk-block--graphite .nel-window { border-color: var(--color-graphite-rule); }
.bars { display: grid; gap: var(--space-2xs); padding: var(--space-xs); }
.bar-row {
  display: grid;
  grid-template-columns: minmax(0, 8rem) minmax(0, 1fr) 2.5rem;
  gap: var(--space-xs);
  align-items: center;
}
.industry {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.3;
  overflow-wrap: anywhere;
}
.industry--lead { font-weight: 600; color: var(--color-accent); }
.track {
  height: 0.75rem;
  position: relative;
  background: var(--color-paper-3);
}
.desk-block--graphite .track { background: var(--color-paper-3); }
.bar {
  height: 0.25rem;
  position: absolute;
  left: 0;
}
.bar.current { top: 0.0625rem; }
.bar.previous { bottom: 0.0625rem; background: var(--color-prior); }
.value {
  color: var(--color-ink);
  text-align: right;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: var(--text-xs);
}
.desk-block--graphite .value { color: var(--color-graphite-ink); }
svg {
  width: 100%;
  height: var(--chart-height);
  display: block;
  overflow: visible;
  padding: 0 var(--space-xs) var(--space-xs);
}
.theme-card {
  padding: var(--space-2xs) var(--space-xs);
  margin: 0;
  border-bottom: var(--rule) solid var(--color-rule);
  background: var(--color-paper-2);
}
.desk-block--graphite .theme-card { border-bottom-color: var(--color-graphite-rule); }
.theme-line { display: block; color: var(--color-ink-2); font-family: var(--font-mono); font-size: var(--text-xs); }
.desk-block--graphite .theme-line { color: var(--color-graphite-muted); }
.theme-line strong { font-size: var(--text-sm); color: var(--color-accent); font-family: var(--font-display); letter-spacing: 0.04em; text-transform: uppercase; }
.desk-block--graphite .theme-line strong { color: var(--color-accent); }
.table-wrap { overflow-x: auto; max-width: 100%; }
.scrollable-table { max-height: 16rem; overflow-y: auto; }
table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.scrollable-table th {
  position: sticky;
  top: 0;
  background: var(--color-paper-3);
  z-index: var(--z-raised);
}
.desk-block--graphite .scrollable-table th { background: var(--color-paper-3); }
th, td {
  padding: var(--space-3xs) var(--space-2xs);
  border-bottom: var(--rule) solid var(--color-rule);
  text-align: right;
  font-size: var(--text-xs);
}
.desk-block--graphite th,
.desk-block--graphite td { border-bottom-color: var(--color-graphite-rule); }
th:first-child, th:nth-child(2), td:first-child, td:nth-child(2) { text-align: left; }
th {
  color: var(--color-accent);
  font-family: var(--font-display);
  font-size: 0.625rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  background: var(--color-paper-3);
}
.desk-block--graphite th { color: var(--color-accent); }
td.col-industry { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--color-muted); }
td.col-rules { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ticker-link {
  font-family: var(--font-outlier);
  font-weight: 600;
  color: var(--color-ink);
  text-decoration: none;
}
.desk-block--graphite .ticker-link { color: var(--color-graphite-ink); }
.high-liquidity { color: var(--color-liquidity); }
tbody tr:nth-child(even) { background: color-mix(in oklch, var(--color-paper-2) 70%, transparent); }
.tick-up { color: var(--color-up); }
.tick-down { color: var(--color-down); }
.ticker-link--earn { box-shadow: inset 0 -2px 0 var(--color-warn); }
.note-input {
  width: 100%;
  min-height: 1.5rem;
  padding: var(--space-3xs) var(--space-2xs);
  background: var(--color-paper-2);
  color: var(--color-ink);
  border-color: var(--color-rule-2);
  text-transform: none;
  letter-spacing: 0;
  font-weight: 400;
}
.desk-block--graphite .note-input {
  background: var(--color-paper);
  color: var(--color-graphite-ink);
  border-color: var(--color-graphite-rule);
}
.empty {
  color: var(--color-muted);
  padding: var(--space-sm) var(--space-xs);
  text-align: left;
  font-family: var(--font-mono);
}
.desk-block--graphite .empty { color: var(--color-graphite-muted); }
.snapshot-date {
  font-family: var(--font-outlier);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-accent-ink);
}
.dashboard-title { margin: 0; }
.foot-line {
  border-top: var(--rule) solid var(--grey-100);
  padding: var(--space-xs) var(--page-gutter);
  max-width: none;
  margin: 0;
  background: var(--grey-800);
}
.foot-line p {
  margin: 0;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (min-width: 40rem) {
  .section-heading { grid-template-columns: minmax(0, 1fr) auto; }
  .section-heading .btn { justify-self: end; }
  .bar-row { grid-template-columns: minmax(0, 11rem) minmax(0, 1fr) 2.5rem; }
}
@media (min-width: 60rem) {
  .rules__groups { grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr); }
  .window-sections { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (min-width: 90rem) {
  .window-sections { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 72rem) {
  .bbg-product { display: none; }
}
@media (max-width: 60rem) {
  .bbg-clock { display: none; }
}
@media (max-width: 47.99rem) {
  .col-industry, .col-vol, .col-ext, .col-rules { display: none; }
  .bbg-keys { display: none; }
  .nav-edge { flex-wrap: wrap; }
  .foot-line p { white-space: normal; }
}
@media (pointer: coarse) {
  .note-input { min-height: var(--control-height); }
}
@media (prefers-reduced-motion: reduce) {
  select, .btn, .note-input, .ticker-link, .skip-link {
    transition: none;
  }
  select:active, .btn:active { transform: none; }
}
  </style>
</head>
<body>
<a class="skip-link" href="#hard-rules">Skip to desk</a>
<main>
  <header class="nav-edge topbar">
    <div class="bbg-brand">
      <a class="wordmark" href="#thematic-title">LLD</a>
      <span class="bbg-product">Liquid Leadership</span>
    </div>
    <nav class="bbg-keys" aria-label="Terminal panels">
      <a href="#hard-rules"><kbd>F1</kbd> Rules</a>
      <a href="#thematic-title"><kbd>F2</kbd> Themes</a>
      <a href="#liquid-title"><kbd>F3</kbd> LL</a>
      <a href="#focus-title"><kbd>F4</kbd> Focus</a>
      <a href="#nel-title"><kbd>F5</kbd> NEL</a>
    </nav>
    <div class="nav-edge__controls">
      <span id="bbg-clock" class="bbg-clock" aria-live="off"></span>
      <label class="visually-hidden" for="date">Snapshot date</label>
      <select id="date" aria-label="Snapshot date"></select>
      <button id="download-image" class="btn btn--primary" type="button">Snap &lt;GO&gt;</button>
    </div>
  </header>
  <p class="lede">Post-close desk · pick Focus · open charts <span id="bbg-session">US equity session</span></p>
  <section id="hard-rules" class="rules" aria-labelledby="rules-title">
    <h2 id="rules-title" class="rules__title">Jeff’s 14 hard rules</h2>
    <div class="rules__groups">
      <div>
        <h3>Pre-trade · 1–8</h3>
        <ol class="rules__list">
          <li><span class="rules__n">1</span><span>No entry if LoD already exceeds ~60% of ATR</span></li>
          <li><span class="rules__n">2</span><span>No entry if ATR% from 50-MA &gt; ~4×</span></li>
          <li><span class="rules__n">3</span><span>Biotechs out of post-market scan; exposure via IBB/XBI through LABU/LABD</span></li>
          <li><span class="rules__n">4</span><span>No entry without substantial RVOL, except mega-cap liquid names</span></li>
          <li><span class="rules__n">5</span><span>Delay ~30 min after the open unless extreme RVOL is already printing</span></li>
          <li><span class="rules__n">6</span><span>No entry ahead of major econ data or pre/post earnings</span></li>
          <li><span class="rules__n">7</span><span>No long against a declining 200-MA</span></li>
          <li><span class="rules__n">8</span><span>No entry into an immediate gap resistance zone</span></li>
        </ol>
      </div>
      <div>
        <h3>Session · 9–14</h3>
        <ol class="rules__list" start="9">
          <li><span class="rules__n">9</span><span>≤ 3 new positions per session</span></li>
          <li><span class="rules__n">10</span><span>Never chase — even one day late. Only optimal entry</span></li>
          <li><span class="rules__n">11</span><span>The more the market rises consecutive days, the more cautious on new longs</span></li>
          <li><span class="rules__n">12</span><span>Once a durable book, prioritize adds to winners already above breakeven</span></li>
          <li><span class="rules__n">13</span><span>Extremely cautious layering risk on gap-up opens</span></li>
          <li><span class="rules__n">14</span><span>Express ideas as longs — shorts via inverse / synthetic long ETFs</span></li>
        </ol>
      </div>
    </div>
  </section>
  <section class="desk-block" aria-labelledby="thematic-title">
    <div class="section-heading"><h1 id="thematic-title" class="dashboard-title">Thematic Leadership</h1></div>
    <div id="leadership-sections" class="window-sections"></div>
  </section>
  <section class="desk-block" aria-labelledby="liquid-title">
    <div class="section-heading">
      <h2 id="liquid-title">Liquid Leaders (LL)</h2>
      <button id="download-ll" class="btn btn--ghost" type="button">Export LL</button>
    </div>
    <div id="liquid-sections" class="window-sections"></div>
  </section>
  <section class="desk-block desk-block--graphite" aria-labelledby="focus-title">
    <div class="section-heading">
      <h2 id="focus-title">Focus Candidates</h2>
      <button id="download-focus" class="btn btn--ghost" type="button">Export Focus</button>
    </div>
    <div id="focus-sections" class="window-sections"></div>
  </section>
  <section class="desk-block" aria-labelledby="nel-title">
    <div class="section-heading">
      <h2 id="nel-title">Non-Extended Leaders (NEL)</h2>
      <button id="download-nel" class="btn btn--ghost" type="button">Export NEL</button>
    </div>
    <div id="nel-sections" class="window-sections"></div>
  </section>
</main>
<footer class="foot-line">
  <p>LLD · Liquid Leadership · not financial advice · kelex</p>
</footer>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script>
const history = __DATA__;
const dateSelect = document.getElementById('date');
const thematicTitle = document.getElementById('thematic-title');
const liquidTitle = document.getElementById('liquid-title');
const nelTitle = document.getElementById('nel-title');
const focusTitle = document.getElementById('focus-title');
const leadershipSections = document.getElementById('leadership-sections');
const liquidSections = document.getElementById('liquid-sections');
const nelSections = document.getElementById('nel-sections');
const focusSections = document.getElementById('focus-sections');
const downloadButton = document.getElementById('download-image');
const downloadLiquidButton = document.getElementById('download-ll');
const downloadNelButton = document.getElementById('download-nel');
const downloadFocusButton = document.getElementById('download-focus');
const flowMeta = { '1m': { label:'1 month', color:'var(--color-frame-1m)' }, '3m': { label:'3 months', color:'var(--color-frame-3m)' }, '6m': { label:'6 months', color:'var(--color-frame-6m)' } };
const rankColors = ['var(--color-rank-1)', 'var(--color-rank-2)', 'var(--color-rank-3)', 'var(--color-rank-4)', 'var(--color-rank-5)'];
const NOTE_KEY = 'nel-note:';

function counts(snapshot, frame) { return snapshot?.groups?.[frame] || {}; }
function total(map) { return Object.values(map).reduce((a,b) => a + b, 0); }
function escapeHTML(value) { return String(value ?? '—').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char])); }
function formatPct(value) { return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '—'; }
function formatNumber(value) { return Number.isFinite(Number(value)) ? Number(value).toFixed(2) : '—'; }
function formatDollarVolume(value) { const amount = Number(value); if (!Number.isFinite(amount) || amount <= 0) return '—'; if (amount >= 1_000_000_000) return `$${Math.ceil(amount / 1_000_000_000)}B`; return `$${Math.ceil(amount / 10_000_000) * 10}M`; }
function averageDollarVolume(row) { return row.average_dollar_volume_30d ?? row.dollar_volume_30d; }
function isTrue(value) { return value === true || String(value).toLowerCase() === 'true'; }
function noteValue(symbol) { try { return localStorage.getItem(NOTE_KEY + symbol) || ''; } catch { return ''; } }
function saveNote(symbol, value) {
  try {
    const key = NOTE_KEY + symbol;
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch { /* private mode */ }
}
function chartUrl(row) {
  const url = String(row.tradingview_url || '').trim();
  if (url) return url;
  const name = String(row.name || '').trim();
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(name)}&interval=D`;
}
function tickerMarkup(row) {
  const name = String(row.name || '').trim();
  const highLiquidity = Number(averageDollarVolume(row)) > 450_000_000;
  const earn = isTrue(row.earnings_soon);
  const title = earn && row.earnings_date ? `Earnings ${String(row.earnings_date)}` : 'Open TradingView chart';
  const classes = `ticker-link${highLiquidity ? ' high-liquidity' : ''}${earn ? ' ticker-link--earn' : ''}`;
  return `<td class="col-ticker"><a class="${classes}" href="${escapeHTML(chartUrl(row))}" target="_blank" rel="noopener noreferrer" title="${escapeHTML(title)}">${escapeHTML(name)}</a></td>`;
}
function noteMarkup(row) {
  const name = String(row.name || '').trim();
  return `<td class="col-note"><label><span class="visually-hidden">Note for ${escapeHTML(name)}</span><input class="note-input" type="text" data-symbol="${escapeHTML(name)}" value="${escapeHTML(noteValue(name))}" autocomplete="off" spellcheck="false" maxlength="240"></label></td>`;
}
function metricCells(row, performance, top) {
  const dollarVolume = averageDollarVolume(row);
  const highLiquidity = Number(dollarVolume) > 450_000_000;
  const lead = top && row.industry === top[0] ? ' industry--lead' : '';
  const move = Number(row[performance]);
  const tick = Number.isFinite(move) && move > 0 ? ' tick-up' : Number.isFinite(move) && move < 0 ? ' tick-down' : '';
  return `${tickerMarkup(row)}<td class="col-industry${lead}">${escapeHTML(row.industry)}</td><td class="col-perf${tick}">${formatPct(row[performance])}</td><td class="col-vol${highLiquidity ? ' high-liquidity' : ''}">${formatDollarVolume(dollarVolume)}</td><td class="col-ext">${formatNumber(row.atr_extension_from_50d)}×</td>`;
}
function focusExtras(row) {
  const score = Number.isFinite(Number(row.focus_score)) ? String(row.focus_score) : '—';
  const passes = Number.isFinite(Number(row.hard_rule_passes)) ? String(row.hard_rule_passes) : '';
  const fails = String(row.hard_rule_fails || '').trim();
  const tight = String(row.tightness_flags || '').trim();
  const rules = [passes ? (fails ? `${passes} · ${fails}` : passes) : fails, tight].filter(Boolean).join(' · ') || '—';
  return `<td class="col-score">${escapeHTML(score)}</td><td class="col-rules">${escapeHTML(rules)}</td>`;
}
function updateDates() {
  dateSelect.innerHTML = history.map((d,i) => `<option value="${i}">${d.date}</option>`).join('');
  dateSelect.value = Math.max(0, history.length - 1);
}
function tickClock() {
  const clock = document.getElementById('bbg-clock');
  if (!clock) return;
  clock.textContent = new Date().toLocaleString('en-US', {
    timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
  }) + ' NY';
}
function currentSnapshot() { return history[Number(dateSelect.value)] || null; }
function renderBars(current, previous, frame, container) {
  const now = counts(current, frame), then = counts(previous, frame);
  const names = [...new Set([...Object.keys(now), ...Object.keys(then)])].sort((a,b) => (now[b]||0) - (now[a]||0) || (then[b]||0) - (then[a]||0)).slice(0, 5);
  if (!names.length) { container.innerHTML = '<p class="empty">No leader data is available for this snapshot.</p>'; return []; }
  const max = Math.max(1, ...names.flatMap(n => [now[n]||0, then[n]||0]));
  container.innerHTML = names.map((name, index) => { const color = rankColors[index]; return `<div class="bar-row"><div class="industry" style="color:${color}" title="${name}">${name}</div><div class="track"><div class="bar current" style="width:${(now[name]||0)/max*100}%;background:${color}" title="Selected: ${now[name]||0}"></div><div class="bar previous" style="width:${(then[name]||0)/max*100}%" title="Prior: ${then[name]||0}"></div></div><div class="value">${now[name]||0}</div></div>`; }).join('');
  return names;
}
function renderTrend(frame, svg, names) {
  const active = history.filter(d => d.groups?.[frame]);
  if (active.length < 2) { svg.innerHTML = '<text x="20" y="45" fill="var(--color-muted)">Add future daily snapshots to see industry leadership trends.</text>'; return; }
  const width = Math.max(620, svg.clientWidth || 900), height = 300, left = 42, right = 28, top = 18, bottom = 34;
  const max = Math.max(1, ...active.flatMap(d => Object.values(counts(d, frame))));
  const x = i => left + i * ((width-left-right) / Math.max(1, active.length-1));
  const y = value => top + (max-value) * ((height-top-bottom)/max);
  let markup = `<line x1="${left}" y1="${height-bottom}" x2="${width-right}" y2="${height-bottom}" stroke="var(--color-rule)"/><line x1="${left}" y1="${top}" x2="${left}" y2="${height-bottom}" stroke="var(--color-rule)"/>`;
  for (let i=0;i<=max;i++) markup += `<text x="${left-8}" y="${y(i)+4}" text-anchor="end" font-size="12" fill="var(--color-ink-2)">${i}</text>`;
  active.forEach((d,i) => markup += `<text x="${x(i)}" y="${height-12}" text-anchor="middle" font-size="12" fill="var(--color-ink-2)">${d.date.slice(5)}</text>`);
  names.forEach((name, index) => { const color = rankColors[index]; const points = active.map((d,i) => `${x(i)},${y(counts(d,frame)[name]||0)}`).join(' '); markup += `<polyline points="${points}" fill="none" stroke="${color}" stroke-width="2.5"/>`; active.forEach((d,i) => markup += `<circle cx="${x(i)}" cy="${y(counts(d,frame)[name]||0)}" r="3" fill="${color}"><title>${escapeHTML(name)}: ${counts(d,frame)[name]||0} on ${d.date}</title></circle>`); });
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`); svg.innerHTML = markup;
}
function windowTables(prefix, heading, extraHead, extraCell, emptyLabel) {
  return Object.entries(flowMeta).map(([frame, meta]) => {
    const extras = extraHead ? extraHead : '';
    return `<section class="nel-window" data-frame="${frame}"><h3>${meta.label} ${heading}</h3><div id="${prefix}-theme-${frame}" class="theme-card frame-${frame}"></div><div class="table-wrap${prefix === 'liquid' ? ' scrollable-table' : ''}"><table><thead><tr><th>Symbol</th><th class="col-industry">Industry</th><th>Performance</th><th class="col-vol">Avg $ Vol</th><th class="col-ext">Extension</th>${extras}<th>Notes</th></tr></thead><tbody id="${prefix}-table-${frame}"></tbody></table></div></section>`;
  }).join('');
}
function fillTheme(id, snapshot, frame) {
  const themeCard = document.getElementById(id);
  if (!themeCard) return null;
  const top = Object.entries(counts(snapshot, frame)).sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0]))[0];
  themeCard.innerHTML = `<span class="theme-line"><strong>${top ? escapeHTML(top[0]) : '—'}</strong>${top ? ` (${top[1]} Liquid Leader${top[1] === 1 ? '' : 's'})` : ''}</span>`;
  return top;
}
function renderTableRows(records, frame, performance, flag, tableId, extraCell, emptyLabel, colspan) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const top = Object.entries(counts(currentSnapshot(), frame)).sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0]))[0];
  const rows = records.filter(row => isTrue(row[flag])).sort((a, b) => {
    const scoreDelta = Number(b.focus_score) - Number(a.focus_score);
    if (extraCell && Number.isFinite(scoreDelta) && scoreDelta) return scoreDelta;
    return Number(b[performance]) - Number(a[performance]);
  });
  table.innerHTML = rows.length ? rows.map(row => `<tr>${metricCells(row, performance, top)}${extraCell ? extraCell(row) : ''}${noteMarkup(row)}</tr>`).join('') : `<tr><td colspan="${colspan}" class="empty">${emptyLabel}</td></tr>`;
}
function renderLiquid(snapshot) {
  const records = snapshot?.liquid || [];
  [['1m', 'Perf.1M', 'is_top_1m'], ['3m', 'Perf.3M', 'is_top_3m'], ['6m', 'Perf.6M', 'is_top_6m']].forEach(([frame, performance, flag]) => {
    fillTheme(`liquid-theme-${frame}`, snapshot, frame);
    renderTableRows(records, frame, performance, flag, `liquid-table-${frame}`, null, 'No liquid leaders.', 6);
  });
}
function renderNEL(snapshot) {
  const records = snapshot?.nel || [];
  [['1m', 'Perf.1M', 'is_top_1m'], ['3m', 'Perf.3M', 'is_top_3m'], ['6m', 'Perf.6M', 'is_top_6m']].forEach(([frame, performance, flag]) => {
    fillTheme(`nel-theme-${frame}`, snapshot, frame);
    renderTableRows(records, frame, performance, flag, `nel-table-${frame}`, null, 'No NEL leaders.', 6);
  });
}
function renderFocus(snapshot) {
  const records = snapshot?.focus || [];
  [['1m', 'Perf.1M', 'is_top_1m'], ['3m', 'Perf.3M', 'is_top_3m'], ['6m', 'Perf.6M', 'is_top_6m']].forEach(([frame, performance, flag]) => {
    fillTheme(`focus-theme-${frame}`, snapshot, frame);
    renderTableRows(records, frame, performance, flag, `focus-table-${frame}`, focusExtras, 'No Focus Candidates.', 8);
  });
}
function render() {
  const current = currentSnapshot(), index = Number(dateSelect.value), previous = history[index-1];
  liquidTitle.textContent = `Liquid Leaders (LL) - ${(current.liquid || []).length} Tickers`;
  nelTitle.textContent = `Non-Extended Leaders (NEL) - ${(current.nel || []).length} Tickers`;
  if (focusTitle) focusTitle.textContent = `Focus Candidates - ${(current.focus || []).length} Tickers`;
  leadershipSections.innerHTML = Object.entries(flowMeta).map(([frame, meta]) => `<section class="panel" data-frame="${frame}"><h2>${meta.label} leadership</h2><div id="bars-${frame}" class="bars"></div><h2 class="trend-label">Leadership over time</h2><svg id="trend-${frame}" role="img" aria-label="${meta.label} industry leader counts across available snapshots"></svg></section>`).join('');
  liquidSections.innerHTML = windowTables('liquid', 'LL', '', null, 'No liquid leaders.');
  if (focusSections) focusSections.innerHTML = windowTables('focus', 'Focus', '<th class="col-score">Score</th><th class="col-rules">Rules</th>', focusExtras, 'No Focus Candidates.');
  nelSections.innerHTML = windowTables('nel', 'NEL', '', null, 'No NEL leaders.');
  Object.keys(flowMeta).forEach(frame => { const rankedNames = renderBars(current, previous, frame, document.getElementById(`bars-${frame}`)); renderTrend(frame, document.getElementById(`trend-${frame}`), rankedNames); });
  renderLiquid(current);
  renderFocus(current);
  renderNEL(current);
}
function downloadSymbols(key, filePrefix) {
  const snapshot = currentSnapshot();
  const symbols = [...new Set((snapshot?.[key] || []).map(row => String(row.name || '').trim()).filter(Boolean))].sort();
  const csv = ['symbol', ...symbols.map(symbol => `"${symbol.replaceAll('"', '""')}"`)].join('\n') + '\n';
  const blob = new Blob([csv], { type:'text/csv;charset=utf-8' });
  const link = document.createElement('a'); link.download = `${filePrefix}_symbols_${snapshot.date}.csv`; link.href = URL.createObjectURL(blob); link.click(); URL.revokeObjectURL(link.href);
}
async function downloadPageImage() {
  if (typeof html2canvas !== 'function') { window.alert('The image exporter could not load. Check your connection and try again.'); return; }
  downloadButton.disabled = true; downloadButton.dataset.state = 'loading'; downloadButton.textContent = 'Creating image…';
  try {
    const canvas = await html2canvas(document.querySelector('main'), { backgroundColor: getComputedStyle(document.body).backgroundColor, scale:2, useCORS:true, windowWidth:document.documentElement.scrollWidth, windowHeight:document.documentElement.scrollHeight, onclone: clonedDocument => { const bar = clonedDocument.querySelector('.topbar'); bar.innerHTML = `<div class="bbg-brand"><a class="wordmark">LLD</a><span class="bbg-product">Liquid Leadership</span></div><span class="snapshot-date">${currentSnapshot().date}</span>`; } });
    const link = document.createElement('a'); link.download = `industry-leadership-${currentSnapshot().date}.png`; link.href = canvas.toDataURL('image/png'); link.click();
  } finally { downloadButton.disabled = false; downloadButton.dataset.state = ''; downloadButton.textContent = 'Snap <GO>'; }
}
document.addEventListener('input', event => {
  const field = event.target.closest('.note-input');
  if (!field || !field.dataset.symbol) return;
  saveNote(field.dataset.symbol, field.value);
});
document.addEventListener('keydown', event => {
  const map = { F1: '#hard-rules', F2: '#thematic-title', F3: '#liquid-title', F4: '#focus-title', F5: '#nel-title' };
  const href = map[event.key];
  if (!href) return;
  event.preventDefault();
  document.querySelector(href)?.scrollIntoView({ behavior: 'instant', block: 'start' });
});
if (!history.length) { document.querySelector('main').innerHTML = '<p class="empty">Run the scanner once to create a momentum-leader snapshot.</p>'; } else { updateDates(); tickClock(); setInterval(tickClock, 1000); dateSelect.addEventListener('change', render); downloadButton.addEventListener('click', downloadPageImage); downloadLiquidButton.addEventListener('click', () => downloadSymbols('liquid', 'liquid_leaders')); downloadNelButton.addEventListener('click', () => downloadSymbols('nel', 'nel')); if (downloadFocusButton) downloadFocusButton.addEventListener('click', () => downloadSymbols('focus', 'focus')); window.addEventListener('resize', render); render(); }
</script>
</body>
</html>'''
    rendered = template.replace("__DATA__", payload)
    dashboard.write_text(rendered, encoding="utf-8")
    pages_entrypoint.write_text(rendered, encoding="utf-8")
    return dashboard
