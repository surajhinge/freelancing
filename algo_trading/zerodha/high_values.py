import pandas as pd
import requests
import os
from datetime import datetime, timedelta
from kiteconnect import KiteConnect

# ========= USER INPUTS ==========
API_KEY = "your_api_key"
API_SECRET = "your_api_secret"
REQUEST_TOKEN = "your_request_token"

instrument_csv = "instruments.csv"
input_excel = "ST_calls_new.xlsx"
output_excel = "ST_calls_new_with_high.xlsx"
interval = "minute"
# =================================

try:
    # Step 1: Login and generate access token
    kite = KiteConnect(api_key=API_KEY)
    data = kite.generate_session(REQUEST_TOKEN, api_secret=API_SECRET)
    access_token = data["access_token"]
    kite.set_access_token(access_token)
    print("✅ Logged in successfully to Zerodha Kite API")

    # Step 2: Download the latest instruments file
    print("\n⬇️ Downloading latest instruments.csv from Zerodha API...")
    url = "https://api.kite.trade/instruments"
    response = requests.get(url, headers={"X-Kite-Version": "3"})
    response.raise_for_status()
    with open(instrument_csv, "wb") as f:
        f.write(response.content)
    print(f"📄 instruments.csv downloaded successfully ({os.path.getsize(instrument_csv)/1024:.2f} KB)\n")

    # Step 3: Load instruments master
    instruments_df = pd.read_csv(instrument_csv)
    print(f"📊 Loaded {len(instruments_df)} instruments")

    # Step 4: Load Excel file with strike names
    st_df = pd.read_excel(input_excel)
    print(f"📘 Loaded {len(st_df)} rows from {input_excel}\n")

    # Step 5: Prepare API headers
    headers = {
        "X-Kite-Version": "3",
        "Authorization": f"token {API_KEY}:{access_token}"
    }

    # Step 6: Iterate through each row and fetch high value
    high_values = []

    for i, row in st_df.iterrows():
        strike_name = str(row["StrikeName"]).strip()
        date_str = str(row["Date"]).strip()
        time_str = str(row["Time"]).strip()

        # Lookup instrument_token
        match = instruments_df[instruments_df["tradingsymbol"] == strike_name]
        if match.empty:
            print(f"⚠️ No instrument found for {strike_name}")
            high_values.append(None)
            continue

        instrument_token = int(match.iloc[0]["instrument_token"])

        # Build from/to timestamps
        from_ts = f"{date_str} {time_str}"
        to_dt = datetime.strptime(from_ts, "%Y-%m-%d %H:%M:%S") + timedelta(seconds=59)
        to_ts = to_dt.strftime("%Y-%m-%d %H:%M:%S")

        url = f"https://api.kite.trade/instruments/historical/{instrument_token}/{interval}"
        params = {
            "from": from_ts,
            "to": to_ts,
            "continuous": 0,
            "oi": 0
        }

        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

            candles = data.get("data", {}).get("candles", [])
            if candles:
                ts, open_, high_, low_, close_, volume_ = candles[0]
                high_values.append(high_)
                print(f"✅ {strike_name} ({instrument_token}) → High={high_} at {ts}")
            else:
                print(f"⚠️ No candle found for {strike_name} at {from_ts}")
                high_values.append(None)

        except Exception as e:
            print(f"❌ Error fetching {strike_name}: {e}")
            high_values.append(None)

    # Step 7: Save results to new Excel file
    st_df["HIGH"] = high_values
    st_df.to_excel(output_excel, index=False)
    print(f"\n✅ All done! Results saved to: {output_excel}")

except Exception as e:
    print(f"\n❌ Script terminated due to error: {e}")

finally:
    # Step 8: Cleanup instruments.csv
    if os.path.exists(instrument_csv):
        os.remove(instrument_csv)
        print(f"🗑️ Deleted temporary file: {instrument_csv}")
