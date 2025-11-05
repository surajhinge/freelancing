# print("Hi there!")

# from pandas_datareader import data as pdr
# import datetime

# start = datetime.datetime(2024,1,10)
# end   = datetime.datetime(2024,1,11)

# df = pdr.get_data_yahoo("TCS.NS", start, end)
# print(df['High'][0])

# import yfinance as yf
# import datetime

# print("Hi there!")

# start = datetime.datetime(2024,1,10)
# end = datetime.datetime(2024,1,11)

# df = yf.download("TCS.NS", start=start, end=end)

# if df.empty:
#     print("No data returned!")
# else:
#     high = df['High'].iloc[0]
#     print("Daily High:", high)


# import yfinance as yf
# import datetime

# print("Fetching TCS High for 30 Oct 2025...")

# # Target date
# target_date = datetime.datetime(2025, 11, 10)
# next_date = datetime.datetime(2025, 11, 11)

# # Download data
# df = yf.download("TCS.NS", start=target_date, end=next_date)

# if df.empty:
#     print("No data found (Market holiday or future date)")
# else:
#     # Extract the float value of the High column
#     high_price = float(df['High'].iloc[0])
#     print(f"High price on 30 Oct 2025: ₹{high_price:.2f}")

# import yfinance as yf
# import datetime

# # Take only 1 input date from user
# date_input = input("Enter date (DD-MM-YYYY): ")

# try:
#     # Convert input to datetime object
#     target_date = datetime.datetime.strptime(date_input, "%d-%m-%Y")
#     next_date = target_date + datetime.timedelta(days=1)

#     print(f"Fetching TCS High for {date_input}...")

#     # Download data only for the given date
#     df = yf.download("TCS.NS", start=target_date, end=next_date)

#     if df.empty:
#         print("No data found (Weekend, holiday, or future date).")
#     else:
#         high_price = float(df['High'].iloc[0])
#         print(f"High price on {date_input}: ₹{high_price:.2f}")

# except ValueError:
#     print("Invalid date format! Please enter date as DD-MM-YYYY.")

import requests
import pandas as pd

def get_nse_stock_high(symbol, date):
    """
    symbol = NSE stock symbol (e.g., TCS, INFY, RELIANCE)
    date = DD-MM-YYYY format
    """

    url = f"https://www.nseindia.com/api/historical/cm/equity?symbol={symbol}&series=[%22EQ%22]&from={date}&to={date}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/"
    }

    sess = requests.Session()
    response = sess.get(url, headers=headers)

    if response.status_code != 200:
        print("❌ Failed to fetch data. NSE site may be blocking requests.")
        return None

    data = response.json().get("data", [])

    if not data:
        print("⚠️ No trading data found (Holiday or wrong date).")
        return None

    df = pd.DataFrame(data)
    df['CH_TRADE_HIGH_PRICE'] = pd.to_numeric(df['CH_TRADE_HIGH_PRICE'], errors='coerce')
    high_price = df['CH_TRADE_HIGH_PRICE'].iloc[0]

    return high_price


# ✅ Take Inputs
symbol = input("Enter stock symbol (e.g., TCS): ").upper()
date = input("Enter date (DD-MM-YYYY): ")

print(f"\nFetching {symbol} HIGH price on {date} from NSE...\n")

high = get_nse_stock_high(symbol, date)

if high is not None:
    print(f"✅ High Price on {date}: ₹{high:.2f}")
