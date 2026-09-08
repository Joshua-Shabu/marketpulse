"""
Pure analytics functions for MarketPulse.

These take plain lists/pandas Series of prices and return derived metrics.
Deliberately kept free of any I/O (no network, no database) so they are
easy to unit test and easy to reuse from both the ingest pipeline and the
API layer.
"""
from __future__ import annotations

from typing import List, Optional

import pandas as pd


def daily_returns(closes: List[float]) -> List[Optional[float]]:
    """Percentage change from the previous close for each price.

    The first element is always None (there is no previous close to
    compare it to). Matches pandas' pct_change semantics but returns a
    plain list of floats/None so callers don't need pandas to consume it.
    """
    series = pd.Series(closes, dtype="float64")
    pct = series.pct_change()
    return [None if pd.isna(v) else float(v) for v in pct]


def moving_average(closes: List[float], window: int) -> List[Optional[float]]:
    """Simple moving average over `window` periods.

    The first (window - 1) elements are None because there isn't enough
    history yet to compute a full window.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    series = pd.Series(closes, dtype="float64")
    ma = series.rolling(window=window, min_periods=window).mean()
    return [None if pd.isna(v) else float(v) for v in ma]


def rolling_volatility(closes: List[float], window: int) -> List[Optional[float]]:
    """Rolling standard deviation of daily returns over `window` periods.

    This is the standard, simple definition of historical volatility used
    for a quick read on how choppy a price series has been recently. Not
    annualized — callers who want an annualized figure can multiply by
    sqrt(252) for daily data themselves.
    """
    if window < 2:
        raise ValueError("window must be >= 2 (volatility needs at least 2 returns)")
    returns = pd.Series(daily_returns(closes), dtype="float64")
    vol = returns.rolling(window=window, min_periods=window).std()
    return [None if pd.isna(v) else float(v) for v in vol]


def latest_summary(closes: List[float], ma_window: int = 5, vol_window: int = 5) -> dict:
    """Convenience wrapper: the most recent price, moving average, and
    volatility reading for a price series, as a single dict. Returns None
    for any figure that doesn't have enough history yet.
    """
    if not closes:
        return {
            "latest_close": None,
            "moving_average": None,
            "volatility": None,
            "daily_return": None,
        }
    ma = moving_average(closes, ma_window)
    vol = rolling_volatility(closes, vol_window)
    ret = daily_returns(closes)
    return {
        "latest_close": closes[-1],
        "moving_average": ma[-1],
        "volatility": vol[-1],
        "daily_return": ret[-1],
    }
