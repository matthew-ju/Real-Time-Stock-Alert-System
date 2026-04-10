#!/usr/bin/env bash
# run_alerts.sh — Launch spy_alert.py only during NYSE trading hours.
#
# NYSE hours: Monday–Friday, 9:30 AM – 4:00 PM Eastern Time.
# This script converts to UTC to avoid local-timezone ambiguity:
#   EDT (Apr–Oct): 13:30–20:00 UTC
#   EST (Nov–Mar): 14:30–21:00 UTC
#
# Usage:
#   bash run_alerts.sh                              # monitor SPY with defaults
#   bash run_alerts.sh --ticker QQQ --percentile 5 # monitor QQQ, top/bottom 5%
#
# The script loops every 60 seconds. When the market opens it launches
# spy_alert.py (which blocks on the WebSocket until disconnected), then waits
# for the next market open.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$SCRIPT_DIR"

log() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $*"
}

# Returns 0 (true) if the current UTC time falls within NYSE trading hours.
is_market_open() {
    local day_of_week
    day_of_week=$(date -u +%u)   # 1=Mon … 5=Fri, 6=Sat, 7=Sun

    # Weekdays only
    [[ "$day_of_week" -ge 1 && "$day_of_week" -le 5 ]] || return 1

    local hour minute time_min
    hour=$(date -u +%H)
    minute=$(date -u +%M)
    time_min=$(( 10#$hour * 60 + 10#$minute ))

    # Use EDT window (13:30–20:00 UTC) as the conservative open range.
    # Adjust OPEN_MIN/CLOSE_MIN seasonally if needed.
    local open_min=$(( 13 * 60 + 30 ))   # 09:30 ET in EDT  = 13:30 UTC
    local close_min=$(( 20 * 60 ))        # 16:00 ET in EDT  = 20:00 UTC

    [[ "$time_min" -ge "$open_min" && "$time_min" -lt "$close_min" ]]
}

main() {
    log "Stock alert scheduler started. Watching for NYSE market hours …"
    log "Python script: $PYTHON_SCRIPT"

    while true; do
        if is_market_open; then
            log "Market is open — launching spy_alert $*"
            cd "$PACKAGE_DIR" && PYTHONPATH=src python3 -m spy_alert "$@" || log "spy_alert.py exited with code $?."
            log "Waiting for next market open …"
        else
            log "Market is closed. Sleeping 60s …"
        fi
        sleep 60
    done
}

main "$@"