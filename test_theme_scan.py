import unittest
from datetime import date

import pandas as pd

from theme_scan import Settings, annotate_display, calculate_leaders, tradingview_url


def _row(**overrides):
    row = {
        "name": "KEEP",
        "description": "Keep Inc",
        "exchange": "NASDAQ",
        "industry": "Technology Services",
        "close": 120,
        "SMA30": 120,
        "SMA50": 100,
        "ADRP": 5,
        "ATRP": 6,
        "Perf.1M": 40,
        "Perf.3M": 60,
        "Perf.6M": 80,
        "average_volume_10d_calc": 500_000,
        "average_volume_30d_calc": 500_000,
    }
    row.update(overrides)
    return row


class CalculateLeadersTests(unittest.TestCase):
    def test_excludes_biotech_and_thin_activity(self):
        raw = pd.DataFrame([
            _row(),
            _row(name="LOW_ADR", ADRP=3.9),
            _row(name="BIOTECH", industry="Biotechnology"),
            _row(name="THIN", average_volume_10d_calc=100_000),
        ])
        universe, leaders = calculate_leaders(raw, Settings(top_pct=1))
        self.assertEqual(set(universe.name), {"KEEP"})
        self.assertEqual(set(leaders.name), {"KEEP"})

    def test_keeps_extended_names_because_themes_need_full_breadth(self):
        """The old NEL extension filter is gone; theme counts use every leader."""
        raw = pd.DataFrame([_row(), _row(name="EXTENDED", close=140, SMA30=140, ATRP=4.5)])
        _, leaders = calculate_leaders(raw, Settings(top_pct=1))
        self.assertEqual(set(leaders.name), {"KEEP", "EXTENDED"})

    def test_reports_extension_as_context_only(self):
        raw = pd.DataFrame([_row()])
        _, leaders = calculate_leaders(raw, Settings(top_pct=1))
        self.assertAlmostEqual(leaders.iloc[0].atr_extension_from_50d, 20 / 6)
        self.assertEqual(leaders.iloc[0].average_dollar_volume_30d, 60_000_000)

    def test_combines_1m_3m_and_6m_leaders_without_duplicates(self):
        raw = pd.DataFrame([
            _row(name="MOM_1M", SMA50=110, ATRP=10, **{"Perf.1M": 50, "Perf.3M": 10, "Perf.6M": 5}),
            _row(name="MOM_3M", SMA50=110, ATRP=10, **{"Perf.1M": 10, "Perf.3M": 50, "Perf.6M": 5}),
            _row(name="MOM_6M", SMA50=110, ATRP=10, **{"Perf.1M": 10, "Perf.3M": 5, "Perf.6M": 50}),
        ])
        _, leaders = calculate_leaders(raw, Settings(top_pct=0.33))
        self.assertEqual(set(leaders.name), {"MOM_1M", "MOM_3M", "MOM_6M"})
        self.assertEqual(len(leaders), 3)

    def test_liquidity_filter_uses_30_day_price_sma(self):
        raw = pd.DataFrame([
            _row(name="PASS", SMA30=100, average_volume_30d_calc=400_000),
            _row(name="FAIL", SMA30=70, average_volume_30d_calc=400_000),
        ])
        universe, _ = calculate_leaders(raw, Settings(top_pct=1))
        self.assertEqual(list(universe.name), ["PASS"])

    def test_top_group_has_an_exact_size_when_performance_values_tie(self):
        raw = pd.DataFrame([
            _row(name=name, **{"Perf.1M": 50, "Perf.3M": 50, "Perf.6M": 50})
            for name in ["AAA", "BBB", "CCC", "DDD"]
        ])
        _, leaders = calculate_leaders(raw, Settings(top_pct=0.25))
        self.assertEqual(list(leaders.name), ["AAA"])

    def test_empty_universe_returns_two_empty_frames(self):
        raw = pd.DataFrame([_row(ADRP=1.0)])
        universe, leaders = calculate_leaders(raw, Settings(top_pct=1))
        self.assertTrue(universe.empty)
        self.assertTrue(leaders.empty)


class AnnotateDisplayTests(unittest.TestCase):
    def test_adds_chart_link_and_flags_near_term_earnings(self):
        raw = pd.DataFrame([
            _row(),
            _row(name="EARN", earnings_release_date="2026-09-18"),
        ])
        _, leaders = calculate_leaders(raw, Settings(top_pct=1))
        annotated = annotate_display(leaders, Settings(), date(2026, 9, 17)).set_index("name")
        self.assertEqual(
            annotated.loc["KEEP", "tradingview_url"],
            "https://www.tradingview.com/chart/?symbol=NASDAQ:KEEP&interval=D",
        )
        self.assertTrue(bool(annotated.loc["EARN", "earnings_soon"]))
        self.assertEqual(annotated.loc["EARN", "earnings_date"], "2026-09-18")
        self.assertFalse(bool(annotated.loc["KEEP", "earnings_soon"]))

    def test_missing_earnings_column_is_not_an_error(self):
        raw = pd.DataFrame([_row()])
        _, leaders = calculate_leaders(raw, Settings(top_pct=1))
        annotated = annotate_display(leaders, Settings(), date(2026, 9, 17))
        self.assertEqual(list(annotated.earnings_date), [""])
        self.assertEqual(list(annotated.earnings_soon), [False])

    def test_empty_frame_passes_through(self):
        annotated = annotate_display(pd.DataFrame(), Settings(), date(2026, 9, 17))
        self.assertTrue(annotated.empty)

    def test_tradingview_url_maps_amex(self):
        self.assertEqual(
            tradingview_url("AMEX", "SPY"),
            "https://www.tradingview.com/chart/?symbol=AMEX:SPY&interval=D",
        )
