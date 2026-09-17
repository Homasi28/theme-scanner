import unittest
from datetime import date

import pandas as pd

from focus_list import FocusSettings, Settings, annotate_structure, calculate_focus, calculate_nel, tradingview_url


class FocusListTests(unittest.TestCase):
    def test_excludes_biotech_and_overextended_leaders(self):
        raw = pd.DataFrame([
            {"name": "KEEP", "industry": "Technology Services", "close": 120, "SMA30": 120, "SMA50": 100, "ADRP": 5, "ATRP": 6, "Perf.1M": 40, "Perf.3M": 60, "Perf.6M": 80, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
            {"name": "EXTENDED", "industry": "Technology Services", "close": 140, "SMA30": 140, "SMA50": 100, "ADRP": 5, "ATRP": 4.5, "Perf.1M": 30, "Perf.3M": 50, "Perf.6M": 70, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
            {"name": "LOW_ADR", "industry": "Technology Services", "close": 150, "SMA30": 150, "SMA50": 100, "ADRP": 3.9, "ATRP": 6, "Perf.1M": 20, "Perf.3M": 40, "Perf.6M": 60, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
            {"name": "BIOTECH", "industry": "Biotechnology", "close": 150, "SMA30": 150, "SMA50": 100, "ADRP": 6, "ATRP": 6, "Perf.1M": 20, "Perf.3M": 40, "Perf.6M": 60, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
        ])
        universe, leaders, focus = calculate_nel(raw, Settings(top_pct=1, max_atr_extension=4))
        self.assertEqual(set(universe.name), {"KEEP", "EXTENDED"})
        self.assertEqual(set(leaders.name), {"KEEP", "EXTENDED"})
        self.assertEqual(list(focus.name), ["KEEP"])
        self.assertAlmostEqual(focus.iloc[0].atr_extension_from_50d, 20 / 6)
        self.assertEqual(focus.iloc[0].average_dollar_volume_30d, 60_000_000)

    def test_combines_1m_3m_and_6m_leaders_without_duplicates(self):
        raw = pd.DataFrame([
            {"name": "MOM_1M", "industry": "Technology Services", "close": 120, "SMA30": 120, "SMA50": 110, "ADRP": 5, "ATRP": 10, "Perf.1M": 50, "Perf.3M": 10, "Perf.6M": 5, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
            {"name": "MOM_3M", "industry": "Technology Services", "close": 120, "SMA30": 120, "SMA50": 110, "ADRP": 5, "ATRP": 10, "Perf.1M": 10, "Perf.3M": 50, "Perf.6M": 5, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
            {"name": "MOM_6M", "industry": "Technology Services", "close": 120, "SMA30": 120, "SMA50": 110, "ADRP": 5, "ATRP": 10, "Perf.1M": 10, "Perf.3M": 5, "Perf.6M": 50, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
        ])
        _, leaders, _ = calculate_nel(raw, Settings(top_pct=0.33, max_atr_extension=100))
        self.assertEqual(set(leaders.name), {"MOM_1M", "MOM_3M", "MOM_6M"})
        self.assertEqual(len(leaders), 3)

    def test_liquidity_filter_uses_30_day_price_sma(self):
        raw = pd.DataFrame([
            {"name": "PASS", "industry": "Technology Services", "close": 120, "SMA30": 100, "SMA50": 100, "ADRP": 5, "ATRP": 10, "Perf.1M": 50, "Perf.3M": 50, "Perf.6M": 50, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 400_000},
            {"name": "FAIL", "industry": "Technology Services", "close": 120, "SMA30": 70, "SMA50": 100, "ADRP": 5, "ATRP": 10, "Perf.1M": 40, "Perf.3M": 40, "Perf.6M": 40, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 400_000},
        ])
        universe, _, _ = calculate_nel(raw, Settings(top_pct=1))
        self.assertEqual(list(universe.name), ["PASS"])

    def test_top_group_has_an_exact_size_when_performance_values_tie(self):
        raw = pd.DataFrame([
            {"name": name, "industry": "Technology Services", "close": 120, "SMA30": 120, "SMA50": 110, "ADRP": 5, "ATRP": 10, "Perf.1M": 50, "Perf.3M": 50, "Perf.6M": 50, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000}
            for name in ["AAA", "BBB", "CCC", "DDD"]
        ])
        _, leaders, _ = calculate_nel(raw, Settings(top_pct=0.25, max_atr_extension=100))
        self.assertEqual(list(leaders.name), ["AAA"])

    def _leader_row(self, **overrides):
        row = {
            "name": "KEEP",
            "description": "Keep Inc",
            "exchange": "NASDAQ",
            "industry": "Technology Services",
            "close": 120,
            "SMA10": 118,
            "SMA20": 116,
            "SMA30": 120,
            "SMA50": 110,
            "SMA100": 105,
            "SMA150": 100,
            "SMA200": 95,
            "EMA10": 119,
            "EMA21": 117,
            "BB.upper": 124,
            "BB.lower": 116,
            "BB.basis": 120,
            "high": 121,
            "low": 119,
            "ADRP": 5,
            "ATRP": 10,
            "ATR": 12,
            "relative_volume_10d_calc": 1.8,
            "gap": 0.2,
            "market_cap_basic": 2_000_000_000,
            "Perf.1M": 40,
            "Perf.3M": 60,
            "Perf.6M": 80,
            "average_volume_10d_calc": 500_000,
            "average_volume_30d_calc": 500_000,
        }
        row.update(overrides)
        return row

    def test_structure_flags_do_not_change_nel_membership(self):
        raw = pd.DataFrame([self._leader_row(), self._leader_row(name="EXTENDED", close=140, SMA30=140, ATRP=4.5)])
        _, leaders, nel = calculate_nel(raw, Settings(top_pct=1, max_atr_extension=4))
        annotated = annotate_structure(nel, FocusSettings(), date(2026, 9, 17))
        self.assertEqual(list(nel.name), ["KEEP"])
        self.assertEqual(list(annotated.name), ["KEEP"])

    def test_focus_keeps_tight_aligned_nel_names(self):
        raw = pd.DataFrame([self._leader_row()])
        _, _, nel = calculate_nel(raw, Settings(top_pct=1, max_atr_extension=4))
        annotated = annotate_structure(nel, FocusSettings(), date(2026, 9, 17))
        focus = calculate_focus(annotated, FocusSettings())
        self.assertEqual(list(focus.name), ["KEEP"])
        self.assertTrue(bool(focus.iloc[0].lod_ok))
        self.assertTrue(bool(focus.iloc[0].ma_aligned))
        self.assertTrue(bool(focus.iloc[0].ema_aligned))
        self.assertTrue(bool(focus.iloc[0].near_ema))
        self.assertTrue(bool(focus.iloc[0].plan_tight))
        self.assertEqual(focus.iloc[0].tradingview_url, "https://www.tradingview.com/chart/?symbol=NASDAQ:KEEP&interval=D")

    def test_focus_requires_ema_alignment_and_a_tightness_flag(self):
        raw = pd.DataFrame([
            self._leader_row(name="UNALIGNED", EMA10=121, EMA21=122),
            self._leader_row(name="STRETCHED", EMA21=90, high=128, low=112, **{"BB.upper": 150, "BB.lower": 90, "BB.basis": 120}),
        ])
        _, _, nel = calculate_nel(raw, Settings(top_pct=1, max_atr_extension=4))
        annotated = annotate_structure(nel, FocusSettings(), date(2026, 9, 17))
        focus = calculate_focus(annotated, FocusSettings())
        self.assertEqual(set(nel.name), {"UNALIGNED", "STRETCHED"})
        self.assertEqual(list(focus.name), [])

    def test_focus_drops_wide_lod_and_earnings_and_below_200(self):
        raw = pd.DataFrame([
            self._leader_row(name="WIDE", high=140, low=100),
            self._leader_row(name="EARN", earnings_release_date="2026-09-18"),
            self._leader_row(name="BELOW", SMA200=130),
        ])
        _, _, nel = calculate_nel(raw, Settings(top_pct=1, max_atr_extension=4))
        annotated = annotate_structure(nel, FocusSettings(), date(2026, 9, 17))
        focus = calculate_focus(annotated, FocusSettings())
        self.assertEqual(set(nel.name), {"WIDE", "EARN", "BELOW"})
        self.assertEqual(list(focus.name), [])

    def test_tradingview_url_maps_amex(self):
        self.assertEqual(
            tradingview_url("AMEX", "SPY"),
            "https://www.tradingview.com/chart/?symbol=AMEX:SPY&interval=D",
        )
