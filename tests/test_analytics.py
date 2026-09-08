"""
Unit tests for app/analytics.py.

Run with:  python3 -m unittest discover -s tests -v
(uses only the standard library's unittest module, no pytest required)
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.analytics import daily_returns, moving_average, rolling_volatility, latest_summary


class TestDailyReturns(unittest.TestCase):
    def test_first_value_is_none(self):
        result = daily_returns([100.0, 110.0, 121.0])
        self.assertIsNone(result[0])

    def test_known_percentage_changes(self):
        result = daily_returns([100.0, 110.0, 99.0])
        self.assertIsNone(result[0])
        self.assertAlmostEqual(result[1], 0.10, places=6)   # 100 -> 110 is +10%
        self.assertAlmostEqual(result[2], -0.10, places=6)  # 110 -> 99 is -10%

    def test_empty_input(self):
        self.assertEqual(daily_returns([]), [])

    def test_single_value_input(self):
        result = daily_returns([50.0])
        self.assertEqual(result, [None])


class TestMovingAverage(unittest.TestCase):
    def test_simple_window(self):
        result = moving_average([1, 2, 3, 4, 5], window=3)
        # first two entries can't form a full 3-period window
        self.assertIsNone(result[0])
        self.assertIsNone(result[1])
        self.assertAlmostEqual(result[2], 2.0)  # avg(1,2,3)
        self.assertAlmostEqual(result[3], 3.0)  # avg(2,3,4)
        self.assertAlmostEqual(result[4], 4.0)  # avg(3,4,5)

    def test_window_of_one_equals_input(self):
        result = moving_average([10, 20, 30], window=1)
        self.assertEqual(result, [10.0, 20.0, 30.0])

    def test_invalid_window_raises(self):
        with self.assertRaises(ValueError):
            moving_average([1, 2, 3], window=0)


class TestRollingVolatility(unittest.TestCase):
    def test_constant_prices_have_zero_volatility(self):
        # a flat price series has zero daily returns, so volatility is 0
        prices = [100.0] * 6
        result = rolling_volatility(prices, window=3)
        # last few entries should be exactly 0 once the window is full
        non_none = [v for v in result if v is not None]
        self.assertTrue(all(math.isclose(v, 0.0, abs_tol=1e-9) for v in non_none))

    def test_invalid_window_raises(self):
        with self.assertRaises(ValueError):
            rolling_volatility([1, 2, 3], window=1)


class TestLatestSummary(unittest.TestCase):
    def test_empty_series(self):
        summary = latest_summary([])
        self.assertIsNone(summary["latest_close"])
        self.assertIsNone(summary["moving_average"])
        self.assertIsNone(summary["volatility"])
        self.assertIsNone(summary["daily_return"])

    def test_populated_series_has_latest_close(self):
        prices = [10, 11, 12, 13, 14, 15, 16]
        summary = latest_summary(prices, ma_window=3, vol_window=3)
        self.assertEqual(summary["latest_close"], 16)
        self.assertIsNotNone(summary["moving_average"])
        self.assertIsNotNone(summary["volatility"])
        self.assertIsNotNone(summary["daily_return"])


if __name__ == "__main__":
    unittest.main()
