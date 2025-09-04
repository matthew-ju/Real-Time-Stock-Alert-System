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

def get_real_time_price():
    params = {
        'symbol': 'SPY',
        'token': FINNHUB_API_KEY
    }
    response = requests.get(FINNHUB_URL, params=params)
    data = response.json()
    
    try:
        price = float(data['c'])  # 'c' is the current price in Finnhub's response
        return price
    except KeyError:
        print("Error fetching real-time price from Finnhub.")
        return None

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

def stock_alert_system():
    top_10_threshold = np.percentile(daily_returns, 90)
    print("Step #2. Top 10% Threshold: ", top_10_threshold)
    bottom_10_threshold = np.percentile(daily_returns, 10)
    print("Step #2. Bottom 10% Threshold: ", bottom_10_threshold)

    real_time_price = get_real_time_price()
    # for testing purposes only
    # real_time_price = 1
    if real_time_price is None:
        return  
    
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

def job():
    est = pytz.timezone('US/Eastern')
    now = datetime.now(est)
    if now.weekday() < 5 and (now.hour > 9 or (now.hour == 9 and now.minute >= 30)) and (now.hour < 16 or (now.hour == 16 and now.minute <= 30)):
        stock_alert_system()

if __name__ == "__main__":
    prepare_data()
    schedule.every(10).seconds.do(job)

    while True:
        schedule.run_pending()
        time.sleep(1)
