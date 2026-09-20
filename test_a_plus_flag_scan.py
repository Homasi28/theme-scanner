import unittest

import numpy as np
import pandas as pd

from a_plus_flag_scan import APlusFlagSettings, score_symbol


class APlusFlagTests(unittest.TestCase):
    def _frame(self, *, mode="coil"):
        """Thrust (90d) → multi-week flag (45d) → last bar (coil / break / extended)."""
        thrust_n, flag_n = 90, 45
        n = thrust_n + flag_n + 1
        idx = pd.bdate_range("2024-01-01", periods=n)
        thrust = np.linspace(50, 100, thrust_n)
        # Mild upward drift in the flag so the 50MA keeps rising (NVDA/MU style)
        flag = np.linspace(93.5, 97.5, flag_n) + np.random.default_rng(7).normal(0, 0.35, flag_n)
        flag = np.clip(flag, 91.5, 98.5)
        if mode == "breakout":
            last = 101.5  # clear thrust/flag pivot (~100.6)
        elif mode == "extended":
            last = 120.0
        else:
            last = 97.0
        closes = np.concatenate([thrust, flag, [last]])
        high = closes + 0.6
        high[thrust_n:-1] = np.minimum(high[thrust_n:-1], 98.5)
        high[-1] = last + 0.8
        low = closes - 0.9
        low[thrust_n:-1] = np.maximum(low[thrust_n:-1], 90.5)
        volume = np.full(n, 1_000_000.0)
        # Heavy volume on thrust, dry in the flag (A++ coil)
        volume[:thrust_n] *= 1.8
        volume[thrust_n:-1] *= 0.45
        volume[-1] = 2_400_000.0 if mode == "breakout" else 650_000.0
        return (
            pd.Series(closes, index=idx),
            pd.Series(high, index=idx),
            pd.Series(low, index=idx),
            pd.Series(volume, index=idx),
        )

    def test_flags_coil_before_breakout(self):
        c, h, l, v = self._frame(mode="coil")
        row = score_symbol("NVDA", c, h, l, v, APlusFlagSettings(min_thrust_pct=15.0))
        self.assertIsNotNone(row)
        self.assertEqual(row["signal"], "APLUS_COIL")
        self.assertGreater(row["thrust_pct"], 15)
        self.assertGreaterEqual(row["dist_to_pivot_pct"], 0)

    def test_day0_breakout_ok(self):
        c, h, l, v = self._frame(mode="breakout")
        row = score_symbol(
            "MU",
            c,
            h,
            l,
            v,
            APlusFlagSettings(min_thrust_pct=15.0, max_dist_above_sma20_pct=20.0),
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["signal"], "APLUS_BREAKOUT")

    def test_rejects_extended_runner(self):
        c, h, l, v = self._frame(mode="extended")
        self.assertIsNone(score_symbol("ASST", c, h, l, v, APlusFlagSettings()))

    def test_rejects_no_thrust(self):
        idx = pd.bdate_range("2024-01-01", periods=160)
        closes = np.linspace(100, 102, 160)
        c = pd.Series(closes, index=idx)
        h, l = c + 0.5, c - 0.5
        v = pd.Series(np.full(160, 1e6), index=idx)
        self.assertIsNone(score_symbol("FLAT", c, h, l, v, APlusFlagSettings()))


if __name__ == "__main__":
    unittest.main()
