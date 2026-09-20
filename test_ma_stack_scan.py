import unittest

import numpy as np
import pandas as pd

from ma_stack_scan import MaStackSettings, score_symbol


class MaStackTests(unittest.TestCase):
    def _close(self, values):
        index = pd.bdate_range("2025-01-01", periods=len(values))
        return pd.Series(values, index=index, dtype=float)

    def test_flags_fresh_20_30_cross_with_5_above_10(self):
        # Flat → soft pullback → sharp ramp so SMA20 flips above SMA30 while 5>10.
        flat = np.full(60, 50.0)
        down = np.linspace(50, 45, 15)
        up = np.linspace(45, 70, 15)
        close = self._close(np.concatenate([flat, down, up]))
        row = score_symbol("X", close, MaStackSettings(cross_lookback_days=8, cross_band_pct=1.0))
        self.assertIsNotNone(row)
        self.assertTrue(row["sma5_gt_sma10"])
        self.assertTrue(row["sma20_gt_sma30"])
        self.assertTrue(str(row["signal"]).startswith("20x30"))
        self.assertIsInstance(row["cross_days_ago"], int)

    def test_rejects_without_5_above_10(self):
        n = 60
        close = self._close(np.linspace(100, 60, n))
        self.assertIsNone(score_symbol("Y", close, MaStackSettings()))


if __name__ == "__main__":
    unittest.main()
