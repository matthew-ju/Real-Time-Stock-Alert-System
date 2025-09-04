# Real-Time-Stock-Alert-System

Real-time stock alert system for monitoring your choice of stock symbols' daily returns in real time and sending SMS alerts when returns reach extreme levels.
For demo purposes, SPY (S&P 500 EFT) is used.

On start, the code downloads ~5 years of SPY daily closes from Yahoo Finance with yfinance, converts them to percent daily returns, and stores them globally. It then sets two alert thresholds using percentiles: the 90th (top 10%) and 10th (bottom 10%) of historical daily returns.

A Finnhub WebSocket subscribes to real-time SPY trades. For each tick, the code computes today’s return vs. yesterday’s close and compares it with those percentile cutoffs. If the return is greater than or equal to the top 10 percentile or less than or equal to the bottom 10 percentile, it sends you an SMS via Twilio. **(env is used to hardcode credentials.)** SSL verification is explicitly disabled for the socket.

Each evaluation also saves a histogram of the last 5 years’ daily return.

An accompanying bash script loops once per minute on weekdays and runs the Python script roughly during market hours (from 01:42 to 16:00 in the script’s system time) to keep the WebSocket listener alive.
