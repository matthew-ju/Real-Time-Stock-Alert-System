"""spy_alert.py — Real-Time SPY Stock Alert System.

Connects to Finnhub's WebSocket feed for live SPY prices. On each trade tick,
computes today's return relative to the previous closing price and sends an SMS
via Twilio if the move lands in the top or bottom N-th percentile of SPY's
historical daily return distribution.

Usage:
    python spy_alert.py [--ticker TICKER] [--percentile N] [--lookback YEARS]

    --ticker      Ticker symbol to monitor (default: SPY)
    --percentile  Alert threshold percentile, e.g. 10 → top/bottom 10% (default: 10)
    --lookback    Years of historical data for threshold calibration (default: 5)

Environment variables (copy .env.example → .env and fill in your values):
    TWILIO_ACCOUNT_SID   Twilio account SID
    TWILIO_AUTH_TOKEN    Twilio auth token
    TWILIO_FROM          Twilio phone number (E.164 format, e.g. +18001234567)
    TWILIO_TO            Destination phone number (E.164 format)
    FINNHUB_API_KEY      Finnhub API key for WebSocket access
"""

import argparse
import json
import logging
import os
import ssl
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import websocket
import yfinance as yf
from dotenv import load_dotenv
from twilio.rest import Client

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

load_dotenv()

DEFAULT_TICKER: str = "SPY"
DEFAULT_PERCENTILE: int = 10        # top/bottom N % triggers an SMS alert
DEFAULT_LOOKBACK_YEARS: int = 5     # years of history used to calibrate thresholds

RECONNECT_DELAY_SECONDS: int = 10
MAX_RECONNECT_ATTEMPTS: int = 5

HISTOGRAM_OUTPUT_PATH: Path = Path("spy-generated-histogram.png")


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------

def _require_env(key: str) -> str:
    """Return the value of an environment variable, raising clearly if absent.

    Args:
        key: The environment variable name.

    Returns:
        The string value of the environment variable.

    Raises:
        EnvironmentError: If the variable is not set or is an empty string.
    """
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            "Copy .env.example → .env and fill in your credentials."
        )
    return value


# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------

def fetch_historical_data(ticker: str, lookback_years: int) -> pd.Series:
    """Download adjusted closing prices for *ticker* over the past *lookback_years* years.

    Uses ``yf.Ticker.history()`` rather than ``yf.download()`` because it hits
    a different Yahoo Finance endpoint that is significantly more reliable and
    avoids the intermittent ``JSONDecodeError`` that affects the bulk-download
    API.  Retries up to 3 times with exponential backoff before giving up.

    Args:
        ticker: The ticker symbol to fetch (e.g. "SPY").
        lookback_years: Number of years of history to retrieve.

    Returns:
        A pandas Series of daily closing prices indexed by date.

    Raises:
        ValueError: If yfinance returns an empty DataFrame after all retries
            (bad ticker or persistent network/API issue).
    """
    period = f"{lookback_years}y"
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        log.info(
            "Fetching %d years of %s history via Ticker.history() "
            "(period=%s, attempt %d/%d) …",
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
            wait = 2 ** attempt  # 2s, 4s
            log.info("Retrying in %ds …", wait)
            time.sleep(wait)

    raise ValueError(
        f"yfinance returned no data for ticker '{ticker}' after {max_attempts} attempts. "
        "Check the symbol and your network connection."
    )


def compute_daily_returns(prices: pd.Series) -> pd.Series:
    """Compute percentage daily returns from a series of closing prices.

    Args:
        prices: Daily closing price series (indexed by date).

    Returns:
        A Series of daily percentage returns with NaN rows dropped.
    """
    return prices.pct_change().dropna() * 100


# ---------------------------------------------------------------------------
# Charting
# ---------------------------------------------------------------------------

def save_histogram(
    daily_returns: pd.Series,
    top_thresh: float,
    bot_thresh: float,
    output_path: Path,
) -> None:
    """Save a histogram of historical daily returns with alert thresholds marked.

    Args:
        daily_returns: Series of historical daily percentage returns.
        top_thresh: Upper alert threshold value (e.g. 90th percentile).
        bot_thresh: Lower alert threshold value (e.g. 10th percentile).
        output_path: File path to write the PNG to.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(daily_returns, bins=50, edgecolor="black", color="#4c72b0", alpha=0.8)
    ax.axvline(
        top_thresh, color="red", linestyle="dashed", linewidth=1.5,
        label=f"Top threshold ({top_thresh:.2f}%)",
    )
    ax.axvline(
        bot_thresh, color="blue", linestyle="dashed", linewidth=1.5,
        label=f"Bottom threshold ({bot_thresh:.2f}%)",
    )
    ax.legend()
    ax.set_title("SPY Daily Return Rates — Last 5 Years")
    ax.set_xlabel("Daily Return (%)")
    ax.set_ylabel("Frequency")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    log.info("Histogram saved → %s", output_path)


# ---------------------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------------------

def send_sms(
    message: str,
    account_sid: str,
    auth_token: str,
    from_phone: str,
    to_phone: str,
) -> str:
    """Send an SMS via Twilio and return the message SID.

    Args:
        message: Body of the SMS.
        account_sid: Twilio account SID.
        auth_token: Twilio auth token.
        from_phone: Twilio sending phone number (E.164 format).
        to_phone: Destination phone number (E.164 format).

    Returns:
        The Twilio message SID string on success.

    Raises:
        twilio.base.exceptions.TwilioRestException: On Twilio API errors.
    """
    client = Client(account_sid, auth_token)
    msg = client.messages.create(body=message, from_=from_phone, to=to_phone)
    log.info("SMS sent (SID: %s)", msg.sid)
    return msg.sid


def evaluate_tick(
    real_time_price: float,
    historical_prices: pd.Series,
    daily_returns: pd.Series,
    percentile: int,
    twilio_creds: dict,
) -> None:
    """Evaluate a real-time price tick and fire an SMS alert if warranted.

    Computes today's return relative to the previous closing price, compares it
    against the historical percentile thresholds, and sends an SMS if the move
    is extreme enough.  Also refreshes the saved histogram on every tick.

    Args:
        real_time_price: Latest trade price from the WebSocket stream.
        historical_prices: Historical closing price series (last value = previous close).
        daily_returns: Historical daily return series used to compute thresholds.
        percentile: Alert percentile boundary (e.g. 10 → top/bottom 10 %).
        twilio_creds: Dict with keys ``account_sid``, ``auth_token``,
            ``from_phone``, and ``to_phone``.
    """
    top_thresh = float(np.percentile(daily_returns, 100 - percentile))
    bot_thresh = float(np.percentile(daily_returns, percentile))

    previous_close = float(historical_prices.iloc[-1])
    return_rate = (real_time_price / previous_close - 1) * 100

    log.info(
        "Tick | price=%.4f  prev_close=%.4f  return=%.4f%%",
        real_time_price, previous_close, return_rate,
    )

    if return_rate >= top_thresh:
        body = (
            f"🚀 SPY is up +{return_rate:.2f}% today — "
            f"top {percentile}% of historical daily moves."
        )
        log.info("Sending UPSIDE alert: %s", body)
        send_sms(body, **twilio_creds)
    elif return_rate <= bot_thresh:
        # Bug fix: return_rate is already negative here — don't double-negate it.
        body = (
            f"📉 SPY is down {return_rate:.2f}% today — "
            f"bottom {percentile}% of historical daily moves."
        )
        log.info("Sending DOWNSIDE alert: %s", body)
        send_sms(body, **twilio_creds)

    save_histogram(daily_returns, top_thresh, bot_thresh, HISTOGRAM_OUTPUT_PATH)


# ---------------------------------------------------------------------------
# WebSocket handlers (closures over shared mutable state)
# ---------------------------------------------------------------------------

def build_handlers(
    historical_prices: pd.Series,
    daily_returns: pd.Series,
    ticker: str,
    percentile: int,
    twilio_creds: dict,
):
    """Return WebSocket event-handler callables bound to the given alert state.

    Using closures keeps all state local and avoids global variables.

    Args:
        historical_prices: Historical closing price series.
        daily_returns: Corresponding daily return series.
        ticker: Ticker symbol being monitored (e.g. "SPY").
        percentile: Alert percentile threshold.
        twilio_creds: Twilio credential dict.

    Returns:
        Tuple of ``(on_open, on_message, on_error, on_close)`` callables
        compatible with ``websocket.WebSocketApp``.
    """

    def on_open(ws: websocket.WebSocketApp) -> None:
        log.info("WebSocket connected — subscribing to %s", ticker)
        ws.send(json.dumps({"type": "subscribe", "symbol": ticker}))

    def on_message(ws: websocket.WebSocketApp, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError as exc:
            log.warning(
                "Could not parse WebSocket message: %.120s — %s", message, exc
            )
            return

        if "data" not in data:
            return

        for item in data["data"]:
            if item.get("s") == ticker:
                try:
                    evaluate_tick(
                        real_time_price=float(item["p"]),
                        historical_prices=historical_prices,
                        daily_returns=daily_returns,
                        percentile=percentile,
                        twilio_creds=twilio_creds,
                    )
                except Exception as exc:  # noqa: BLE001
                    log.error("Error processing tick: %s", exc, exc_info=True)

    def on_error(ws: websocket.WebSocketApp, error: Exception) -> None:
        log.error("WebSocket error: %s", error)

    def on_close(
        ws: websocket.WebSocketApp,
        status_code: Optional[int],
        msg: Optional[str],
    ) -> None:
        log.info("WebSocket closed (status=%s msg=%s)", status_code, msg)

    return on_open, on_message, on_error, on_close


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Real-Time SPY Stock Alert System — sends an SMS when SPY's intraday "
            "return hits an extreme historical percentile."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--ticker",
        default=DEFAULT_TICKER,
        help="Ticker symbol to monitor.",
    )
    parser.add_argument(
        "--percentile",
        type=int,
        default=DEFAULT_PERCENTILE,
        help="Alert threshold percentile (e.g. 10 → top/bottom 10%%).",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=DEFAULT_LOOKBACK_YEARS,
        dest="lookback_years",
        help="Years of historical data used to calibrate alert thresholds.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Fetch historical data, then open a Finnhub WebSocket with auto-reconnect."""
    args = parse_args()

    # Load credentials — fail fast with a clear message if any are missing.
    twilio_creds = {
        "account_sid": _require_env("TWILIO_ACCOUNT_SID"),
        "auth_token":  _require_env("TWILIO_AUTH_TOKEN"),
        "from_phone":  _require_env("TWILIO_FROM"),
        "to_phone":    _require_env("TWILIO_TO"),
    }
    finnhub_key = _require_env("FINNHUB_API_KEY")
    ws_url = f"wss://ws.finnhub.io?token={finnhub_key}"

    # Fetch historical data once at startup (avoids redundant API calls per tick).
    historical_prices = fetch_historical_data(args.ticker, args.lookback_years)
    daily_returns = compute_daily_returns(historical_prices)

    log.info(
        "Ready | %d trading days | top-%d%% threshold=%.4f%% | bottom-%d%% threshold=%.4f%%",
        len(daily_returns),
        args.percentile,
        float(np.percentile(daily_returns, 100 - args.percentile)),
        args.percentile,
        float(np.percentile(daily_returns, args.percentile)),
    )

    on_open, on_message, on_error, on_close = build_handlers(
        historical_prices, daily_returns, args.ticker, args.percentile, twilio_creds
    )

    # WebSocket loop with bounded auto-reconnect on unexpected disconnection.
    attempts = 0
    while attempts < MAX_RECONNECT_ATTEMPTS:
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        # cert_reqs=CERT_NONE works around Finnhub's certificate chain issues on some
        # macOS/Linux environments; revisit if your system verifies certs correctly.
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        attempts += 1
        if attempts < MAX_RECONNECT_ATTEMPTS:
            log.warning(
                "WebSocket disconnected. Reconnecting in %ds (attempt %d/%d) …",
                RECONNECT_DELAY_SECONDS,
                attempts,
                MAX_RECONNECT_ATTEMPTS,
            )
            time.sleep(RECONNECT_DELAY_SECONDS)

    log.error("Max reconnect attempts (%d) reached. Exiting.", MAX_RECONNECT_ATTEMPTS)


if __name__ == "__main__":
    main()
