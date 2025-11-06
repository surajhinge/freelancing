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

# import requests
# import pandas as pd

# def get_nse_stock_high(symbol, date):
#     """
#     symbol = NSE stock symbol (e.g., TCS, INFY, RELIANCE)
#     date = DD-MM-YYYY format
#     """

#     url = f"https://www.nseindia.com/api/historical/cm/equity?symbol={symbol}&series=[%22EQ%22]&from={date}&to={date}"

#     headers = {
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
#         "Accept": "application/json",
#         "Referer": "https://www.nseindia.com/"
#     }

#     sess = requests.Session()
#     response = sess.get(url, headers=headers)

#     if response.status_code != 200:
#         print("❌ Failed to fetch data. NSE site may be blocking requests.")
#         return None

#     data = response.json().get("data", [])

#     if not data:
#         print("⚠️ No trading data found (Holiday or wrong date).")
#         return None

#     df = pd.DataFrame(data)
#     df['CH_TRADE_HIGH_PRICE'] = pd.to_numeric(df['CH_TRADE_HIGH_PRICE'], errors='coerce')
#     high_price = df['CH_TRADE_HIGH_PRICE'].iloc[0]

#     return high_price


# # ✅ Take Inputs
# symbol = input("Enter stock symbol (e.g., TCS): ").upper()
# date = input("Enter date (DD-MM-YYYY): ")

# print(f"\nFetching {symbol} HIGH price on {date} from NSE...\n")

# high = get_nse_stock_high(symbol, date)

# if high is not None:
#     print(f"✅ High Price on {date}: ₹{high:.2f}")


# import requests
# import pandas as pd

# headers = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
#     "Accept": "application/json",
#     "Referer": "https://www.nseindia.com/"
# }


# def fetch_equity_high(symbol, date):
#     url = f"https://www.nseindia.com/api/historical/cm/equity?symbol={symbol}&series=[%22EQ%22]&from={date}&to={date}"
#     resp = requests.get(url, headers=headers)

#     if resp.status_code != 200:
#         return None

#     data = resp.json().get("data", [])
#     if not data:
#         return None

#     df = pd.DataFrame(data)
#     return float(df["CH_TRADE_HIGH_PRICE"].iloc[0])


# def fetch_future_high(symbol, expiry, date):
#     url = f"https://www.nseindia.com/api/historical/fo/derivatives?symbol={symbol}&expiryDate={expiry}&from={date}&to={date}&instrumentType=FUTSTK"
#     resp = requests.get(url, headers=headers)

#     if resp.status_code != 200:
#         return None

#     data = resp.json().get("data", [])
#     if not data:
#         return None

#     df = pd.DataFrame(data)
#     return float(df["HIGH_PRICE"].iloc[0])


# def fetch_option_high(symbol, expiry, strike, opttype, date):
#     url = (
#         "https://www.nseindia.com/api/historical/fo/derivatives?"
#         f"symbol={symbol}&expiryDate={expiry}&strikePrice={strike}"
#         f"&optionType={opttype}&from={date}&to={date}&instrumentType=OPTSTK"
#     )
#     resp = requests.get(url, headers=headers)

#     if resp.status_code != 200:
#         return None

#     data = resp.json().get("data", [])
#     if not data:
#         return None

#     df = pd.DataFrame(data)
#     return float(df["HIGH_PRICE"].iloc[0])


# # ✅ User Input Handling

# print("\nSelect Segment:")
# print("1️⃣ Equity (Stocks)")
# print("2️⃣ Futures")
# print("3️⃣ Options\n")

# choice = input("Enter 1/2/3: ").strip()

# symbol = input("Enter symbol (e.g. TCS, RELIANCE): ").upper()
# date = input("Enter date (DD-MM-YYYY): ")

# if choice == "1":
#     high = fetch_equity_high(symbol, date)
#     segment = "Equity"

# elif choice == "2":
#     expiry = input("Enter expiry date (e.g. 30-Nov-2023): ")
#     high = fetch_future_high(symbol, expiry, date)
#     segment = "Futures"

# elif choice == "3":
#     expiry = input("Enter expiry date (e.g. 30-Nov-2023): ")
#     strike = input("Enter strike price (e.g. 3500): ")
#     opttype = input("Enter option type (CE/PE): ").upper()
#     high = fetch_option_high(symbol, expiry, strike, opttype, date)
#     segment = f"Options ({opttype}) @ {strike}"

# else:
#     print("❌ Invalid choice")
#     exit()


# if high is None:
#     print(f"\n⚠️ No data found for {symbol} on {date} (Holiday or wrong symbol/fields)")
# else:
#     print(f"\n✅ {segment} HIGH on {date}")
#     print(f"👉 Symbol: {symbol}")
#     print(f"💹 High Price: ₹{high:.2f}")


# from upstox import *
# from datetime import datetime, timedelta


# # ----------------------------------------
# # ✅ Replace these with your credentials
# API_KEY = "YOUR_API_KEY"
# ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
# # ----------------------------------------

# u = Upstox(API_KEY, ACCESS_TOKEN)

# # ✅ Set exchange to NSE
# u.get_master_contract("NSE_EQ")

# symbol = "SBIN"

# # ✅ Enter specific date (Example: 01 Nov 2024)
# target_date = datetime.datetime(2024, 11, 1)

# # ✅ OHLC requires +1 day for end range
# next_day = target_date + datetime.timedelta(days=1)

# # ✅ Fetch OHLC data
# data = u.get_ohlc(
#     u.get_instrument_by_symbol("NSE_EQ", symbol),
#     OHLCInterval.Day_1,
#     target_date,
#     next_day
# )

# if not data:
#     print("⚠️ No data found (Holiday or incorrect symbol)")
# else:
#     high_price = data[0].high
#     print(f"📈 High Price for {symbol} on {target_date.strftime('%d-%m-%Y')}: ₹{high_price:.2f}")


import requests
from datetime import datetime, timedelta

API_KEY = "YOUR_API_KEY"
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"
INSTRUMENT_KEY = "NSE_EQ|3045"  # SBIN

date_str = "01-11-2024"  # Example
date_obj = datetime.strptime(date_str, "%d-%m-%Y")
next_day = date_obj + timedelta(days=1)

url = (
    f"https://api.upstox.com/v2/market-data/ohlc?"
    f"instrument_key={INSTRUMENT_KEY}&interval=day&"
    f"from={date_obj.date()}&to={next_day.date()}"
)

headers = {
    "Api-Version": "2.0",
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}

response = requests.get(url, headers=headers)
data = response.json()

try:
    high = data["data"]["ohlc"][0]["high"]
    print(f"High for SBIN on {date_str}: ₹{high}")
except:
    print("No data available for the date — market holiday or incorrect date.")
