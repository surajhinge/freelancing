import requests
import datetime
from kiteconnect import KiteConnect

API_KEY = "your_api_key"
API_SECRET = "your_api_secret"
REQUEST_TOKEN = "your_request_token"

# Step 1: obtain access_token
kite = KiteConnect(api_key=API_KEY)
data = kite.generate_session(request_token=REQUEST_TOKEN, api_secret=API_SECRET)
access_token = data["access_token"]
kite.set_access_token(access_token)

# Step 2: define instrument and time-window
instrument_token = 30147842
interval = "minute"
# from and to both the same minute
from_ts = "2025-10-30 09:35:00"
to_ts   = "2025-10-30 09:35:59"

# Step 3: fetch historical data
url = f"https://api.kite.trade/instruments/historical/{instrument_token}/{interval}"
headers = {
    "X-Kite-Version": "3",
    "Authorization": f"token {API_KEY}:{access_token}"
}
params = {
    "from": from_ts,
    "to": to_ts,
    "continuous": 0,
    "oi": 0
}
resp = requests.get(url, headers=headers, params=params)
resp.raise_for_status()
respj = resp.json()

# Step 4: parse and print the high price
candles = respj["data"]["candles"]
if not candles:
    print("No candle returned for given time.")
else:
    # each candle: [timestamp, open, high, low, close, volume]
    ts, open_, high_, low_, close_, volume_ = candles[0]
    print(f"High price at {ts} is {high_}")
