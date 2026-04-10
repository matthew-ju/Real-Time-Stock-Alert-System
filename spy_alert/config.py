"""Global configuration constants and environment-variable helpers."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Alert tuning — override any of these in .env without touching code.
# CLI flags (--ticker, --percentile, --lookback) take precedence if provided.
# ---------------------------------------------------------------------------

DEFAULT_TICKER: str = os.getenv("TICKER", "SPY")
DEFAULT_PERCENTILE: int = int(os.getenv("PERCENTILE", "10"))    # top/bottom N% triggers SMS
DEFAULT_LOOKBACK_YEARS: int = int(os.getenv("LOOKBACK_YEARS", "5"))  # calibration window

# ---------------------------------------------------------------------------
# WebSocket resilience
# ---------------------------------------------------------------------------

RECONNECT_DELAY_SECONDS: int = 10
MAX_RECONNECT_ATTEMPTS: int = 5

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

# Histogram filename reflects the configured ticker so multiple runs don't overwrite each other.
HISTOGRAM_OUTPUT_PATH: Path = Path(f"{DEFAULT_TICKER.lower()}-return-histogram.png")


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------

def require_env(key: str) -> str:
    """Return the value of an environment variable, raising clearly if absent.

    Args:
        key: The environment variable name.

    Returns:
        The non-empty string value of the variable.

    Raises:
        EnvironmentError: If the variable is unset or empty.
    """
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            "Copy .env.example → .env and fill in your credentials."
        )
    return value
