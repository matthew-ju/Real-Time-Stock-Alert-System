# Real-Time Stock Alert System

A production-style Python service that monitors any ticker in real time via a **Finnhub WebSocket** feed, compares each trade against a **statistically calibrated threshold** derived from 5 years of historical returns, and fires an instant **SMS alert via Twilio** whenever the move lands in an extreme percentile of the historical distribution.

Built as a demonstration of applied financial data engineering: streaming data ingestion, statistical signal generation, and reliable alerting — all surfaced through a clean CLI.

---

## How It Works

```
Yahoo Finance (historical)          Finnhub (real-time)
        │                                  │
        ▼                                  ▼
 5 years of SPY closes  ──►  WebSocket tick stream (live price)
        │                                  │
        │   compute percentile             │   compute today's return
        │   thresholds (10th / 90th) ◄─────┘   vs. previous close
        │
        ▼
 Is today's return in the top or bottom N %?
        │
       YES ──► Send SMS via Twilio  +  Save histogram PNG
        │
       NO  ──► Log tick, continue listening
```

**Key design decisions:**
- Historical data is fetched **once at startup** and held in memory — thresholds are computed in O(1) via NumPy percentile, so latency per tick is minimal.
- WebSocket handlers are implemented as **closures** over shared state rather than globals, keeping the code thread-safe and testable.
- The main loop includes **automatic reconnection** (up to 5 attempts, exponential backoff) so the service recovers gracefully from transient network failures.
- All secrets are loaded from environment variables via `python-dotenv` — no credentials ever appear in source code.

---

## Features

| Feature | Details |
|---|---|
| **Real-time data** | Finnhub WebSocket stream — sub-second trade-level ticks |
| **Statistical alerting** | Percentile-based thresholds calibrated on 5 years of historical daily returns |
| **SMS notifications** | Twilio Messaging API — alerts sent immediately when threshold is crossed |
| **Configurable CLI** | `--ticker`, `--percentile`, `--lookback` flags; no code changes needed to switch assets |
| **Auto-reconnect** | Bounded retry loop with exponential backoff on WebSocket disconnection |
| **Structured logging** | `logging` module with timestamps and severity levels |
| **Histogram output** | Matplotlib chart saved on every tick showing the return distribution and current thresholds |

---

## Return Distribution

The chart below shows SPY's historical daily return distribution over the last 5 years with the alert thresholds marked. An SMS fires whenever the current day's return crosses either dashed line.

![SPY Daily Return Rate Histogram](spy-generated-histogram.png)

---

## Tech Stack

- **Python 3.9+**
- [`yfinance`](https://github.com/ranaroussi/yfinance) — historical OHLCV data from Yahoo Finance
- [`websocket-client`](https://github.com/websocket-client/websocket-client) — Finnhub real-time WebSocket feed
- [`twilio`](https://www.twilio.com/docs/libraries/python) — SMS delivery
- [`pandas`](https://pandas.pydata.org/) / [`numpy`](https://numpy.org/) — return computation and percentile analysis
- [`matplotlib`](https://matplotlib.org/) — distribution visualization
- [`python-dotenv`](https://github.com/theskumar/python-dotenv) — environment variable management

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/matthew-ju/Real-Time-Stock-Alert-System.git
cd Real-Time-Stock-Alert-System
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Open `.env` and fill in the four values:

```ini
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx   # Twilio Console home page
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx      # Twilio Console home page
TWILIO_FROM=+18001234567                                # Your Twilio phone number
TWILIO_TO=+12135550123                                  # Your personal phone number
FINNHUB_API_KEY=your_key_here                           # finnhub.io/dashboard
```

**Where to get each credential:**
- **Twilio SID + Token** → [console.twilio.com](https://console.twilio.com) under *Account Info*
- **TWILIO_FROM** → Console → Phone Numbers → Manage → Active Numbers
- **TWILIO_TO** → Your own mobile number (must be verified on a Twilio trial account)
- **Finnhub key** → [finnhub.io/dashboard](https://finnhub.io/dashboard) → API Keys

### 3. Run

```bash
# Monitor SPY with default settings (top/bottom 10%, 5-year lookback)
python spy_alert.py

# Monitor QQQ, alert on top/bottom 5% moves, using 3 years of history
python spy_alert.py --ticker QQQ --percentile 5 --lookback 3
```

#### Scheduler (weekdays only, NYSE market hours)

```bash
# Automatically starts the alert service only during market hours (Mon–Fri 9:30 AM–4:00 PM ET)
bash execute_stock_SPY_alerts.sh

# Pass through CLI args
bash execute_stock_SPY_alerts.sh --ticker QQQ --percentile 5
```

---

## CLI Reference

```
usage: spy_alert.py [-h] [--ticker TICKER] [--percentile PERCENTILE] [--lookback LOOKBACK]

options:
  --ticker      Ticker symbol to monitor            (default: SPY)
  --percentile  Alert threshold percentile (1–49)   (default: 10)
  --lookback    Years of historical data to use     (default: 5)
```

---

## Example Output

```
2026-04-09 09:31:02 [INFO] Fetching 5 years of SPY history via Ticker.history() (period=5y, attempt 1/3) …
2026-04-09 09:31:04 [INFO] Ready | 1255 trading days | top-10% threshold=1.1042% | bottom-10% threshold=-1.0318%
2026-04-09 09:31:04 [INFO] WebSocket connected — subscribing to SPY
2026-04-09 09:31:05 [INFO] Tick | price=541.2300  prev_close=539.1500  return=0.3858%
2026-04-09 09:35:12 [INFO] Tick | price=528.4100  prev_close=539.1500  return=-1.9946%
2026-04-09 09:35:12 [INFO] Sending DOWNSIDE alert: 📉 SPY is down -1.99% today — bottom 10% of historical daily moves.
2026-04-09 09:35:13 [INFO] SMS sent (SID: SMxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx)
2026-04-09 09:35:13 [INFO] Histogram saved → spy-generated-histogram.png
```

---

## Project Structure

```
Real-Time-Stock-Alert-System/
├── spy_alert.py               # Core application — data fetch, alerting, WebSocket handlers, CLI
├── execute_stock_SPY_alerts.sh  # Scheduler: launches spy_alert.py on NYSE weekday hours only
├── requirements.txt           # Pinned Python dependencies
├── .env.example               # Template for required environment variables
├── spy-generated-histogram.png  # Return distribution chart (auto-updated on each run)
└── SPY-daily-quotes.csv       # Reference historical dataset
```

---

## Security Notes

- `.env` is listed in `.gitignore` and **never committed to version control**
- All credentials are loaded at runtime from environment variables
- If deploying to a server, use a secrets manager (AWS Secrets Manager, GCP Secret Manager, etc.) instead of a `.env` file

---

## License

MIT
