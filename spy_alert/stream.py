"""Finnhub WebSocket handler factory."""

import json
import logging
from typing import Optional

import pandas as pd
import websocket

from spy_alert.alerts import evaluate_tick

log = logging.getLogger(__name__)


def build_handlers(
    historical_prices: pd.Series,
    daily_returns: pd.Series,
    ticker: str,
    percentile: int,
    twilio_creds: dict,
):
    """Return WebSocket event handlers bound to the given alert state.

    Handlers are implemented as closures so all state is local — no globals
    needed, and the factory is straightforward to unit-test.

    Args:
        historical_prices: Historical closing price series.
        daily_returns: Corresponding daily return series.
        ticker: Ticker symbol being monitored (e.g. ``"SPY"``).
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
            log.warning("Could not parse message: %.120s — %s", message, exc)
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
