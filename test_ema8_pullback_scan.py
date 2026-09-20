import unittest

import numpy as np
import pandas as pd

from ema8_pullback_scan import Ema8PullbackSettings, score_symbol


class Ema8PullbackTests(unittest.TestCase):
    def _series(self, values, start="2024-01-01"):
        index = pd.bdate_range(start=start, periods=len(values))
        return pd.Series(values, index=index, dtype=float)

    def test_flags_pullback_into_rising_weekly_ema(self):
        # Grind higher, spike, then ease back toward the still-rising EMA.
        weeks = 48
        weekly = np.linspace(40, 90, weeks - 4)
        weekly = np.concatenate([weekly, np.array([96.0, 94.0, 93.0, 92.5])])
        closes = np.repeat(weekly, 5)
        close = self._series(closes)
        high = close * 1.02
        low = close * 0.99
        # Recompute after construction to place the last close on the live EMA band.
        frame = pd.DataFrame({"close": close, "high": high, "low": low})
        weekly_bars = frame.resample("W-FRI").agg({"close": "last", "high": "max", "low": "min"}).dropna()
        ema = weekly_bars["close"].ewm(span=8, adjust=False).mean()
        # Soften the final weekly close toward EMA while keeping EMA rising.
        target = float(ema.iloc[-2]) * 1.004
        closes[-5:] = target
        close = self._series(closes)
        high = close * 1.01
        low = close * 0.995
        settings = Ema8PullbackSettings(touch_pct=4.0, max_undercut_pct=2.0, min_off_high_pct=0.5, min_weeks=20)
        row = score_symbol("TEST", close, high, low, settings, {"exchange": "NASDAQ", "industry": "Software"})
        self.assertIsNotNone(row)
        self.assertTrue(row["ema8w_rising"])
        self.assertEqual(row["signal"], "EMA8W_PB")
        self.assertLessEqual(abs(row["dist_to_ema8w_pct"]), settings.touch_pct)

    def test_rejects_extended_above_ema(self):
        weeks = 40
        weekly = np.linspace(40, 120, weeks)
        closes = np.repeat(weekly, 5)
        # Spike the last close far above the weekly path.
        closes[-1] = float(closes[-1]) * 1.2
        close = self._series(closes)
        high = close * 1.01
        low = close * 0.99
        settings = Ema8PullbackSettings(touch_pct=3.0, min_weeks=20)
        self.assertIsNone(score_symbol("HOT", close, high, low, settings))

    def test_rejects_falling_ema(self):
        weeks = 40
        weekly = np.linspace(120, 60, weeks)
        closes = np.repeat(weekly, 5)
        close = self._series(closes)
        high = close * 1.01
        low = close * 0.99
        settings = Ema8PullbackSettings(min_weeks=20)
        self.assertIsNone(score_symbol("DOWN", close, high, low, settings))


if __name__ == "__main__":
    unittest.main()
