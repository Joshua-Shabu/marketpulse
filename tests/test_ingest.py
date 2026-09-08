"""
Unit tests for the parsing (Transform) and storage (Load) halves of
app/ingest.py and app/db.py.

Deliberately does NOT test fetch_fred_series() (the Extract/network half)
— that function is a thin wrapper around requests.get() with no branching
logic of its own, and hitting the real network in a test would make the
suite flaky and dependent on being online (and on a real API key being
set). Everything with real logic downstream of the network call is
covered here with a synthetic FRED-shaped JSON payload standing in for
what the API would return.

Run with:  python3 -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import db
from app.ingest import parse_fred_observations, run_ingest

SAMPLE_PAYLOAD = {
    "realtime_start": "2026-01-01",
    "realtime_end": "2026-01-01",
    "observation_start": "1600-01-01",
    "observation_end": "9999-12-31",
    "units": "lin",
    "output_type": 1,
    "file_type": "json",
    "order_by": "observation_date",
    "sort_order": "asc",
    "count": 4,
    "offset": 0,
    "limit": 100000,
    "observations": [
        {"realtime_start": "2026-01-01", "realtime_end": "2026-01-01", "date": "2026-01-02", "value": "71.50"},
        {"realtime_start": "2026-01-01", "realtime_end": "2026-01-01", "date": "2026-01-03", "value": "72.10"},
        # FRED represents a missing reading (e.g. a market holiday) as "."
        {"realtime_start": "2026-01-01", "realtime_end": "2026-01-01", "date": "2026-01-04", "value": "."},
        {"realtime_start": "2026-01-01", "realtime_end": "2026-01-01", "date": "2026-01-05", "value": "69.85"},
    ],
}


class TestParseFredObservations(unittest.TestCase):
    def test_parses_all_valid_rows(self):
        rows = parse_fred_observations(SAMPLE_PAYLOAD)
        # 4 observations in, one is "." (missing), so 3 valid rows out
        self.assertEqual(len(rows), 3)

    def test_parses_expected_fields(self):
        rows = parse_fred_observations(SAMPLE_PAYLOAD)
        first = rows[0]
        self.assertEqual(first["date"], "2026-01-02")
        self.assertEqual(first["close"], 71.50)
        # FRED only gives one value per date — no open/high/low/volume
        self.assertIsNone(first["open"])
        self.assertIsNone(first["high"])
        self.assertIsNone(first["low"])
        self.assertIsNone(first["volume"])

    def test_skips_missing_value_marker(self):
        rows = parse_fred_observations(SAMPLE_PAYLOAD)
        dates = [r["date"] for r in rows]
        self.assertNotIn("2026-01-04", dates)

    def test_empty_observations_returns_empty_list(self):
        self.assertEqual(parse_fred_observations({"observations": []}), [])

    def test_missing_observations_key_returns_empty_list(self):
        self.assertEqual(parse_fred_observations({}), [])


class TestRunIngestApiKeyHandling(unittest.TestCase):
    def setUp(self):
        self.conn = db.init_db(":memory:")
        # make sure a leftover env var from a previous test doesn't leak in
        self._old_key = os.environ.pop("FRED_API_KEY", None)

    def tearDown(self):
        self.conn.close()
        if self._old_key is not None:
            os.environ["FRED_API_KEY"] = self._old_key

    def test_raises_clear_error_when_no_api_key_configured(self):
        with self.assertRaises(ValueError) as ctx:
            run_ingest("DCOILWTICO", self.conn)
        self.assertIn("FRED_API_KEY", str(ctx.exception))


class TestDbRoundTrip(unittest.TestCase):
    """Uses an in-memory SQLite database so tests don't touch disk or
    leave files behind."""

    def setUp(self):
        self.conn = db.init_db(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_upsert_then_read_back(self):
        rows = parse_fred_observations(SAMPLE_PAYLOAD)
        written = db.upsert_rows(self.conn, "DCOILWTICO", rows)
        self.assertEqual(written, 3)

        symbols = db.get_symbols(self.conn)
        self.assertEqual(symbols, ["DCOILWTICO"])

        closes = db.get_closes(self.conn, "DCOILWTICO")
        self.assertEqual(
            closes,
            [("2026-01-02", 71.50), ("2026-01-03", 72.10), ("2026-01-05", 69.85)],
        )

    def test_upsert_is_idempotent_on_same_date(self):
        rows = parse_fred_observations(SAMPLE_PAYLOAD)
        db.upsert_rows(self.conn, "DCOILWTICO", rows)
        # re-ingesting the same day with a revised value should UPDATE,
        # not duplicate the row
        db.upsert_rows(self.conn, "DCOILWTICO", [{"date": "2026-01-05", "open": None,
                                                     "high": None, "low": None,
                                                     "close": 70.00, "volume": None}])
        closes = dict(db.get_closes(self.conn, "DCOILWTICO"))
        self.assertEqual(len(closes), 3)  # still 3 rows, not 4
        self.assertEqual(closes["2026-01-05"], 70.00)  # updated value

    def test_get_closes_respects_limit(self):
        rows = parse_fred_observations(SAMPLE_PAYLOAD)
        db.upsert_rows(self.conn, "DCOILWTICO", rows)
        closes = db.get_closes(self.conn, "DCOILWTICO", limit=2)
        self.assertEqual(len(closes), 2)
        # should be the two MOST RECENT dates, oldest-first within that window
        self.assertEqual([d for d, _ in closes], ["2026-01-03", "2026-01-05"])

    def test_unknown_symbol_returns_empty(self):
        self.assertEqual(db.get_closes(self.conn, "does-not-exist"), [])


if __name__ == "__main__":
    unittest.main()
