"""Historical price data fetching and daily return computation."""

import logging
import time

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)


def fetch_historical_data(ticker: str, lookback_years: int) -> pd.Series:
    """Fetch daily closing prices for *ticker* over the past *lookback_years* years.

    Uses ``yf.Ticker.history()`` rather than ``yf.download()`` because it hits
    a more reliable Yahoo Finance endpoint. Retries up to 3 times with
    exponential backoff before raising.

    Args:
        ticker: Ticker symbol to fetch (e.g. ``"SPY"``).
        lookback_years: Number of years of history to retrieve.

    Returns:
        A pandas Series of daily closing prices indexed by date.

    Raises:
        ValueError: If no data is returned after all retry attempts.
    """
    period = f"{lookback_years}y"
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        log.info(
            "Fetching %d years of %s history (period=%s, attempt %d/%d) …",
            lookback_years, ticker, period, attempt, max_attempts,
        )
        try:
            df = yf.Ticker(ticker).history(period=period)
            if not df.empty:
                return df["Close"]
            log.warning("Attempt %d returned empty DataFrame.", attempt)
        except Exception as exc:  # noqa: BLE001
            log.warning("Attempt %d raised %s: %s", attempt, type(exc).__name__, exc)

        if attempt < max_attempts:
            wait = 2 ** attempt  # 2 s, 4 s
            log.info("Retrying in %ds …", wait)
            time.sleep(wait)

    raise ValueError(
        f"yfinance returned no data for '{ticker}' after {max_attempts} attempts. "
        "Check the symbol and your network connection."
    )


def compute_daily_returns(prices: pd.Series) -> pd.Series:
    """Compute percentage daily returns from a closing-price series.

    Args:
        prices: Daily closing price series indexed by date.

    Returns:
        Series of daily percentage returns with the first (NaN) row dropped.
    """
    return prices.pct_change().dropna() * 100
