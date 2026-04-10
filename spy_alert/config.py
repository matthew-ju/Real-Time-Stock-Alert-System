"""Global configuration constants and environment-variable helpers."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Alert tuning
# ---------------------------------------------------------------------------

DEFAULT_TICKER: str = "SPY"
DEFAULT_PERCENTILE: int = 10        # top/bottom N% triggers an SMS alert
DEFAULT_LOOKBACK_YEARS: int = 5     # years of history used to calibrate thresholds

# ---------------------------------------------------------------------------
# WebSocket resilience
# ---------------------------------------------------------------------------

RECONNECT_DELAY_SECONDS: int = 10
MAX_RECONNECT_ATTEMPTS: int = 5

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

HISTOGRAM_OUTPUT_PATH: Path = Path("spy-generated-histogram.png")


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
