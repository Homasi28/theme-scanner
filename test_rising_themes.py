import unittest

from industry_flow_dashboard import (
    detect_rising_themes,
    rising_industry_names,
)


class ThemeBasketTests(unittest.TestCase):
    def test_basket_expansion_is_flagged_separately_from_industries(self):
        rising = detect_rising_themes(
            {"1m": {}},
            {"1m": {}},
            current_baskets={"1m": {"AI Memory": 3}},
            prior_baskets={"1m": {"AI Memory": 1}},
        )
        row = next(r for r in rising if r["industry"] == "AI Memory")
        self.assertEqual(row["kind"], "basket")
        self.assertEqual(row["signal"], "KICKOFF")
        self.assertEqual(row["delta"], 2)

    def test_baskets_do_not_leak_into_industry_highlighting(self):
        rising = detect_rising_themes(
            {"1m": {}},
            {"1m": {}},
            current_baskets={"1m": {"AI Memory": 3}},
            prior_baskets={"1m": {"AI Memory": 1}},
        )
        self.assertNotIn("AI Memory", rising_industry_names(rising, frame="1m"))

    def test_baskets_are_optional(self):
        rising = detect_rising_themes({"1m": {"Semiconductors": 3}}, {"1m": {"Semiconductors": 1}})
        self.assertTrue(all(row["kind"] != "basket" for row in rising))


class RisingThemeTests(unittest.TestCase):
    def test_semis_breadth_expansion_flags_rising(self):
        prior = {"1m": {"Semiconductors": 2, "Packaged Software": 4}}
        current = {"1m": {"Semiconductors": 3, "Packaged Software": 6, "Precious Metals": 1}}
        rising = detect_rising_themes(current, prior)
        names = {row["industry"]: row for row in rising if row["frame"] == "1m"}
        self.assertEqual(names["Semiconductors"]["signal"], "RISING")
        self.assertEqual(names["Semiconductors"]["delta"], 1)
        self.assertEqual(names["Packaged Software"]["signal"], "RISING")
        self.assertNotIn("Precious Metals", names)

    def test_kickoff_when_theme_appears_with_breadth(self):
        prior = {"1m": {"Packaged Software": 5}}
        current = {"1m": {"Packaged Software": 5, "Semiconductors": 3}}
        rising = detect_rising_themes(current, prior)
        semis = next(row for row in rising if row["industry"] == "Semiconductors")
        self.assertEqual(semis["signal"], "KICKOFF")

    def test_semis_complex_cluster_rolls_up(self):
        prior = {
            "1m": {
                "Semiconductors": 2,
                "Computer Peripherals": 1,
            }
        }
        current = {
            "1m": {
                "Semiconductors": 3,
                "Computer Peripherals": 2,
                "Electronic Production Equipment": 1,
            }
        }
        rising = detect_rising_themes(current, prior)
        cluster = next(row for row in rising if row["industry"] == "Semis complex")
        self.assertEqual(cluster["kind"], "cluster")
        self.assertGreaterEqual(cluster["delta"], 1)
        self.assertIn("Semiconductors", rising_industry_names(rising, frame="1m"))


if __name__ == "__main__":
    unittest.main()
