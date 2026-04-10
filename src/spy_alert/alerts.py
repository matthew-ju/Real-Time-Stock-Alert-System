"""Twilio SMS dispatch and per-tick alert evaluation."""

import logging

import numpy as np
import pandas as pd
from twilio.rest import Client

from spy_alert.chart import save_histogram
from spy_alert.config import HISTOGRAM_OUTPUT_PATH

log = logging.getLogger(__name__)


def send_sms(
    message: str,
    account_sid: str,
    auth_token: str,
    from_phone: str,
    to_phone: str,
) -> str:
    """Send an SMS via Twilio and return the resulting message SID.

    Args:
        message: Body text of the SMS.
        account_sid: Twilio account SID.
        auth_token: Twilio auth token.
        from_phone: Twilio sending number (E.164 format).
        to_phone: Destination number (E.164 format).

    Returns:
        Twilio message SID string.

    Raises:
        twilio.base.exceptions.TwilioRestException: On API errors.
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
    """Evaluate a live price tick and fire an SMS alert if the move is extreme.

    Computes today's return vs. the previous close, compares it against the
    historical percentile thresholds, and sends an SMS if warranted.
    Refreshes the saved histogram on every tick.

    Args:
        real_time_price: Latest trade price from the WebSocket stream.
        historical_prices: Historical close series (last value = previous close).
        daily_returns: Historical daily return series for threshold computation.
        percentile: Alert boundary (e.g. 10 → top/bottom 10%).
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
        body = (
            f"📉 SPY is down {return_rate:.2f}% today — "
            f"bottom {percentile}% of historical daily moves."
        )
        log.info("Sending DOWNSIDE alert: %s", body)
        send_sms(body, **twilio_creds)

    save_histogram(daily_returns, top_thresh, bot_thresh, HISTOGRAM_OUTPUT_PATH)
