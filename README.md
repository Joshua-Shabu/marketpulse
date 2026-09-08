# MarketPulse

A small Python ETL pipeline + REST API for daily commodity/economic price
data and derived analytics (moving average, rolling volatility, daily return).

Built to close a real gap for a job application asking for "proficiency in
Python for backend development (services, APIs, data processing)" — rather
than claim that on a resume without evidence, this is an actual working
project that does exactly that.

## What it does

- **Extract**: pulls daily observations for a commodity/economic series
  from the [Federal Reserve's public FRED API](https://fred.stlouisfed.org/docs/api/fred/)
  — a free, official, well-documented data source (requires a free API
  key). Useful daily energy-commodity series include `DCOILWTICO` (WTI
  crude oil), `DCOILBRENTEU` (Brent crude), and `DHHNGSP` (Henry Hub
  natural gas).
- **Transform**: parses FRED's JSON response into clean rows, skipping
  FRED's "." placeholder for missing readings (e.g. market holidays), and
  computes daily returns, a simple moving average, and rolling volatility.
- **Load**: stores price history in a local SQLite database, keyed by
  `(series_id, date)` so re-ingesting a day updates it instead of
  duplicating it.
- **Serve**: a FastAPI service exposes the data and analytics over HTTP.

## Project layout

```
marketpulse/
  app/
    analytics.py   # pure functions: daily_returns, moving_average, rolling_volatility
    db.py          # SQLite storage (init, upsert, read)
    ingest.py       # Extract (network, FRED) + Transform (parsing), orchestrated by run_ingest()
    main.py         # FastAPI app wiring the above into HTTP endpoints
  tests/
    test_analytics.py   # unit tests for the pure analytics functions
    test_ingest.py       # unit tests for FRED-payload parsing + DB round-trips (no network)
  .env.example
  requirements.txt
```

## Setup

1. Get a free FRED API key: https://fred.stlouisfed.org/docs/api/api_key.html
   (a short form, key is issued immediately).
2. Copy `.env.example` to `.env` and paste your key in:
   ```bash
   cp .env.example .env
   # then edit .env so it reads: FRED_API_KEY=your_real_key_here
   ```
3. Install dependencies:
   ```bash
   cd marketpulse
   python3 -m venv .venv
   source .venv/bin/activate        # on Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

`.env` is listed in `.gitignore` so your real key never gets committed.

## Run the tests

The analytics and parsing/storage logic is covered by 21 unit tests using
only Python's built-in `unittest` module (no pytest install required):

```bash
python3 -m unittest discover -s tests -v
```

These tests use synthetic data — a hand-written JSON payload standing in
for what FRED returns, and an in-memory SQLite database — so they run
offline and don't need a real API key or network access.

**Honest note on test coverage**: the tests above cover every function that
has real logic in it. The one function that is *not* unit tested is
`fetch_fred_series()` in `app/ingest.py` — it's a thin wrapper around
`requests.get()` with no branching logic — and the FastAPI route layer in
`main.py` (which just wires already-tested functions to HTTP verbs/paths).
Those two were verified by actually running the server and hitting the
live endpoints (see below), not by an automated test.

## Run the API

```bash
uvicorn app.main:app --reload
```

Then, in another terminal:

```bash
# Pull real data for WTI crude oil
curl -X POST http://127.0.0.1:8000/ingest/DCOILWTICO

# List series you've ingested
curl http://127.0.0.1:8000/symbols

# Raw price history
curl http://127.0.0.1:8000/prices/DCOILWTICO

# Derived analytics (5-day moving average and volatility by default)
curl http://127.0.0.1:8000/analytics/DCOILWTICO

# Try a different window
curl "http://127.0.0.1:8000/analytics/DCOILWTICO?window=10"
```

FastAPI also serves interactive docs at `http://127.0.0.1:8000/docs` once
the server is running.

## Why this project switched data sources mid-build

The first version of this project used Stooq's free CSV endpoint instead
of FRED. That endpoint turned out to no longer work the way it was
expected to (even a plain browser request returned nothing) — an error on
the initial research, not something environment-specific. Rather than keep
guessing at an undocumented endpoint's current behavior, the project was
switched to the Federal Reserve's official, versioned, documented FRED
API, which is a more defensible and stable choice for something meant to
actually keep working.
