import unittest
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from rs_lead_scan import RSLeadSettings, score_symbol


class RSLeadScanTests(unittest.TestCase):
    def _series(self, values, start="2024-01-01"):
        index = pd.bdate_range(start=start, periods=len(values))
        return pd.Series(values, index=index, dtype=float)

    def test_rs_lead_when_rs_high_but_price_below_high(self):
        # Stock flat under prior high while SPY weakens → RS makes a new high first.
        n = 80
        spy = self._series(np.linspace(100, 90, n))
        close = self._series([50.0] * n)
        high = self._series([52.0] * n)
        settings = RSLeadSettings(lookback_daily=60, lookback_weekly=12, min_bars=40, price_buffer_pct=0.5)
        row = score_symbol("TEST", close, high, spy, settings, {"exchange": "NASDAQ", "industry": "Software"})
        self.assertIsNotNone(row)
        self.assertTrue(row["rs_new_high_d"])
        self.assertFalse(row["price_new_high_d"])
        self.assertTrue(row["rs_lead_d"])
        self.assertTrue(row["is_rs_lead"])
        self.assertIn(row["signal"], {"LEAD_D", "LEAD_D_W", "LEAD_W"})

    def test_skips_when_both_price_and_rs_are_at_highs_only_if_not_rs(self):
        n = 80
        spy = self._series([100.0] * n)
        close = self._series(np.linspace(40, 50, n))
        high = close.copy()
        settings = RSLeadSettings(lookback_daily=60, lookback_weekly=12, min_bars=40)
        row = score_symbol("RUN", close, high, spy, settings)
        # RS and price both at highs → still an RS new high, but not a lead.
        self.assertIsNotNone(row)
        self.assertTrue(row["rs_new_high_d"])
        self.assertTrue(row["price_new_high_d"])
        self.assertFalse(row["rs_lead_d"])
        self.assertFalse(row["is_rs_lead"] and row["signal"].startswith("LEAD") and not row["rs_lead_w"])

    def test_returns_none_without_rs_new_high(self):
        n = 80
        spy = self._series(np.linspace(100, 110, n))
        close = self._series(np.linspace(50, 45, n))
        high = close + 1
        settings = RSLeadSettings(lookback_daily=60, lookback_weekly=12, min_bars=40)
        self.assertIsNone(score_symbol("WEAK", close, high, spy, settings))


if __name__ == "__main__":
    unittest.main()
