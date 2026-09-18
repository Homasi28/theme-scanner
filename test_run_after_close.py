import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts.run_after_close import next_session_date


NY = ZoneInfo("America/New_York")


class NextSessionDateTests(unittest.TestCase):
    def test_friday_post_close_stamps_monday(self):
        now = datetime(2026, 9, 18, 17, 22, tzinfo=NY)
        self.assertEqual(next_session_date(now).isoformat(), "2026-09-21")

    def test_thursday_post_close_stamps_friday(self):
        now = datetime(2026, 9, 17, 16, 15, tzinfo=NY)
        self.assertEqual(next_session_date(now).isoformat(), "2026-09-18")

    def test_skips_weekend_into_holiday_monday(self):
        # 2026-09-07 is Labor Day (first Monday in September)
        now = datetime(2026, 9, 4, 16, 15, tzinfo=NY)  # Friday before Labor Day
        self.assertEqual(next_session_date(now).isoformat(), "2026-09-08")


if __name__ == "__main__":
    unittest.main()
