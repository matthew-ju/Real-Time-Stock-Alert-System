import yfinance as yf
import pandas as pd
import numpy as np
import json
import websocket
import ssl
from twilio.rest import Client
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pytz
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()  # reads .env in the project root

def env(key):
    v = os.getenv(key)
    if not v:
        raise RuntimeError(f"Missing required env var: {key}")
    return v

ACCOUNT_SID = env("TWILIO_ACCOUNT_SID")
AUTH_TOKEN  = env("TWILIO_AUTH_TOKEN")
FROM_PHONE  = env("TWILIO_FROM")
TO_PHONE    = env("TWILIO_TO")
FINNHUB_API_KEY = env("FINNHUB_API_KEY")
FINNHUB_WEBSOCKET_URL = f'wss://ws.finnhub.io?token={FINNHUB_API_KEY}'


def get_historical_data():
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=5*365)
    spy = yf.download('SPY', start=start_date, end=end_date)
    return spy['Close']

def calculate_daily_returns(data):
    daily_returns = data.pct_change().dropna() * 100
    return daily_returns

def send_sms_alert(message):
    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    message = client.messages.create(
        body=message,
        from_=FROM_PHONE,
        to=TO_PHONE
    )
    return message.sid

def prepare_data():
    global historical_data, daily_returns
    historical_data = get_historical_data()
    daily_returns = calculate_daily_returns(historical_data)
    print("Step #1. Done with getting and calculating historical daily return rates from Yahoo Finance.")

def stock_alert_system(real_time_price):
    top_10_threshold = np.percentile(daily_returns, 90)
    print("Step #2. Top 10% Threshold: ", top_10_threshold)
    bottom_10_threshold = np.percentile(daily_returns, 10)
    print("Step #2. Bottom 10% Threshold: ", bottom_10_threshold)

    print("Step #3. Real time price: ", real_time_price)
    previous_close = historical_data.iloc[-1]
    print("Step #3. Previous close: ", previous_close)
    return_rate = (real_time_price / previous_close - 1) * 100
    print("Step #3. Return rate: ", return_rate)

    if return_rate >= top_10_threshold:
        message = f"SPY rose +{return_rate:.2f}% today, which is within the top 10% of SPY's daily return rates. -Matthew"
        send_sms_alert(message)
        print("Step #4.  >= top 10% ")
    elif return_rate <= bottom_10_threshold:
        message = f"SPY fell -{return_rate:.2f}% today, which is within the bottom 10% of SPY's daily return rates. -Matthew"
        send_sms_alert(message)
        print("Step #4.  <= bottom 10% ")

    plt.hist(daily_returns, bins=50, edgecolor='black')
    plt.axvline(top_10_threshold, color='red', linestyle='dashed', linewidth=1, label='Top 10% threshold')
    plt.axvline(bottom_10_threshold, color='blue', linestyle='dashed', linewidth=1, label='Bottom 10% threshold')
    plt.legend()
    plt.title('SPY Daily Return Rates Histogram (Last 5 Years)')
    plt.xlabel('Daily Return Rate (%)')
    plt.ylabel('Frequency')
    plt.savefig('spy-generated-histogram.png')
    plt.close()
    print("Step #5. Histogram created.")

def on_message(ws, message):
    data = json.loads(message)
    if 'data' in data:
        for item in data['data']:
            if item['s'] == 'SPY':
                real_time_price = item['p']
                # Just for testing purposes
                # real_time_price = 1000000
                stock_alert_system(real_time_price)

def on_error(ws, error):
    print(f"Websocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("Websocket Closed.")

def on_open(ws):
    ws.send(json.dumps({'type': 'subscribe', 'symbol': 'SPY'}))

if __name__ == "__main__":
    prepare_data()
    ws = websocket.WebSocketApp(FINNHUB_WEBSOCKET_URL,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})  # Disables SSL certificate verification unless you will get certificate error.
