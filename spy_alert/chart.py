"""Histogram generation for the historical return distribution."""

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

log = logging.getLogger(__name__)


def save_histogram(
    daily_returns: pd.Series,
    top_thresh: float,
    bot_thresh: float,
    output_path: Path,
) -> None:
    """Save a histogram of daily returns with alert threshold lines marked.

    Args:
        daily_returns: Historical daily percentage return series.
        top_thresh: Upper alert threshold value (e.g. 90th percentile).
        bot_thresh: Lower alert threshold value (e.g. 10th percentile).
        output_path: Destination file path for the PNG.
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
