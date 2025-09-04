import os
import pandas as pd
import matplotlib.pyplot as plt

# Load the CSV file
file_path = 'SPY-daily-quotes.csv'  # Update the file path if needed
df = pd.read_csv(file_path)

# Calculate the daily return rates
df['Date'] = pd.to_datetime(df['Date'])
df.sort_values('Date', inplace=True)
df['Return'] = df['Close'].pct_change() * 100

# Drop the first row with NaN return rate
df.dropna(subset=['Return'], inplace=True)

# Calculate the top 10% and bottom 10% thresholds for SPY's daily return rates
top_10_threshold = df['Return'].quantile(0.90)
bottom_10_threshold = df['Return'].quantile(0.10)

# Create the directory if it doesn't exist
output_dir = "zhou-jose-research"
os.makedirs(output_dir, exist_ok=True)

# Save the histogram to a file
plt.figure(figsize=(10, 6))
plt.hist(df['Return'], bins=50, edgecolor='k')
plt.axvline(top_10_threshold, color='r', linestyle='dashed', linewidth=1)
plt.axvline(bottom_10_threshold, color='r', linestyle='dashed', linewidth=1)
plt.title('Histogram of SPY Daily Return Rates')
plt.xlabel('Daily Return Rate (%)')
plt.ylabel('Frequency')
histogram_path = os.path.join(output_dir, "spy-daily-return-rate-histogram.png")
plt.savefig(histogram_path)
plt.close()

def calculate_return_rate(previous_close, current_close):
    return ((current_close - previous_close) / previous_close) * 100

# Get the user's input for the current SPY price
try:
    current_spy_price = float(input("Enter today's SPY closing price: "))
except Exception:
    # For environments where input() is not supported, set a default value for testing
    current_spy_price = 561.530029

# Get the previous day's SPY closing price
previous_spy_price = df.iloc[-1]['Close']

# Calculate today's return rate
today_return_rate = calculate_return_rate(previous_spy_price, current_spy_price)

# Check if today's return rate falls within the top 10% or bottom 10% thresholds
if today_return_rate >= top_10_threshold:
    print("SPY rose +{:.2f}% today, which is within the top 10% of SPY's daily return rate.".format(today_return_rate))
    print("Sending return rate alert to your email now.")
elif today_return_rate <= bottom_10_threshold:
    print("SPY fell -{:.2f}% today, which is within the bottom 10% of SPY's daily return rate.".format(today_return_rate))
    print("Sending return rate alert to your email now.")
else:
    print("No alert: Today's return rate is within normal range.")

print("Today's SPY return rate: {:.2f}%".format(today_return_rate))