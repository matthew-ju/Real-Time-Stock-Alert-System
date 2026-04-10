"""Command-line interface and top-level application orchestration."""

import argparse
import logging
import ssl
import time

import numpy as np
import websocket

from spy_alert.config import (
    DEFAULT_LOOKBACK_YEARS,
    DEFAULT_PERCENTILE,
    DEFAULT_TICKER,
    MAX_RECONNECT_ATTEMPTS,
    RECONNECT_DELAY_SECONDS,
    require_env,
)
from spy_alert.data import compute_daily_returns, fetch_historical_data
from spy_alert.stream import build_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Real-Time Stock Alert System — SMS when intraday returns hit extreme percentiles.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--ticker", default=DEFAULT_TICKER,
        help="Ticker symbol to monitor.",
    )
    parser.add_argument(
        "--percentile", type=int, default=DEFAULT_PERCENTILE,
        help="Alert threshold percentile (e.g. 10 → top/bottom 10%%).",
    )
    parser.add_argument(
        "--lookback", type=int, default=DEFAULT_LOOKBACK_YEARS, dest="lookback_years",
        help="Years of historical data for threshold calibration.",
    )
    return parser.parse_args()


def main() -> None:
    """Fetch historical data, calibrate thresholds, and open a WebSocket stream."""
    args = parse_args()

    # Fail fast if any credential is missing before touching any API.
    twilio_creds = {
        "account_sid": require_env("TWILIO_ACCOUNT_SID"),
        "auth_token":  require_env("TWILIO_AUTH_TOKEN"),
        "from_phone":  require_env("TWILIO_FROM"),
        "to_phone":    require_env("TWILIO_TO"),
    }
    finnhub_key = require_env("FINNHUB_API_KEY")
    ws_url = f"wss://ws.finnhub.io?token={finnhub_key}"

    # Fetch once at startup — thresholds computed per-tick in O(1).
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

    # Bounded reconnect loop — backs off on transient disconnections.
    attempts = 0
    while attempts < MAX_RECONNECT_ATTEMPTS:
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        attempts += 1
        if attempts < MAX_RECONNECT_ATTEMPTS:
            log.warning(
                "WebSocket disconnected. Reconnecting in %ds (attempt %d/%d) …",
                RECONNECT_DELAY_SECONDS, attempts, MAX_RECONNECT_ATTEMPTS,
            )
            time.sleep(RECONNECT_DELAY_SECONDS)

    log.error("Max reconnect attempts (%d) reached. Exiting.", MAX_RECONNECT_ATTEMPTS)
