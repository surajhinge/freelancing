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

import yfinance as yf
import datetime

# Take only 1 input date from user
date_input = input("Enter date (DD-MM-YYYY): ")

try:
    # Convert input to datetime object
    target_date = datetime.datetime.strptime(date_input, "%d-%m-%Y")
    next_date = target_date + datetime.timedelta(days=1)

    print(f"Fetching TCS High for {date_input}...")

    # Download data only for the given date
    df = yf.download("TCS.NS", start=target_date, end=next_date)

    if df.empty:
        print("No data found (Weekend, holiday, or future date).")
    else:
        high_price = float(df['High'].iloc[0])
        print(f"High price on {date_input}: ₹{high_price:.2f}")

except ValueError:
    print("Invalid date format! Please enter date as DD-MM-YYYY.")

