import pandas as pd
import requests
import os
from datetime import datetime, timedelta
from kiteconnect import KiteConnect
import logging
import sys
import traceback

# ================= LOG SETUP ==================
LOG_FILE = "zerodha_log.txt"

logging.basicConfig(
    filename=LOG_FILE,
    filemode="w",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True                # <<< IMPORTANT FIX
)

def log(msg, level="info"):
    try:
        print(msg, flush=True)    # <<< ALWAYS PRINT
        sys.stdout.flush()        # <<< IMMEDIATE FLUSH
    except:
        pass

    # Write to log file
    if level == "debug":
        logging.debug(msg)
    elif level == "warning":
        logging.warning(msg)
    elif level == "error":
        logging.error(msg)
    else:
        logging.info(msg)


log("\n================ SCRIPT STARTED ================\n")

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
    # Step 1: Login
    log("🔐 Generating access token...")

    kite = KiteConnect(api_key=API_KEY)
    data = kite.generate_session(REQUEST_TOKEN, api_secret=API_SECRET)
    access_token = data["access_token"]
    kite.set_access_token(access_token)

    log("✅ Logged in successfully to Zerodha Kite API")
    log(f"🔐 Access Token: {access_token}", "debug")

    # Step 2: Download instruments file
    log("\n⬇️ Downloading latest instruments.csv from Zerodha API...")

    url = "https://api.kite.trade/instruments"
    response = requests.get(url, headers={"X-Kite-Version": "3"})
    response.raise_for_status()

    with open(instrument_csv, "wb") as f:
        f.write(response.content)

    log(f"📄 instruments.csv downloaded ({os.path.getsize(instrument_csv)/1024:.2f} KB)")

    # Step 3: Load instruments
    instruments_df = pd.read_csv(instrument_csv)
    log(f"📊 Loaded {len(instruments_df)} instruments")

    # Step 4: Load Excel
    st_df = pd.read_excel(input_excel)
    log(f"📘 Loaded {len(st_df)} rows from {input_excel}")

    # Step 5: Prepare headers
    headers = {
        "X-Kite-Version": "3",
        "Authorization": f"token {API_KEY}:{access_token}"
    }

    high_values = []

    # Step 6: Iterate rows
    for i, row in st_df.iterrows():

        log("\n------------------------------")
        log(f"🔍 Processing row {i+1}")

        strike_name = str(row["StrikeName"]).strip()
        raw_date = str(row["Date"])
        raw_time = str(row["Time"]).strip()

        # Debug prints
        log(f"➡ Raw DATE: {raw_date}", "debug")
        log(f"➡ Raw TIME: {raw_time}", "debug")

        # Parse date
        try:
            parsed_date = pd.to_datetime(raw_date, dayfirst=True)
            clean_date = parsed_date.strftime("%Y-%m-%d")
            log(f"✔ Parsed Date → {clean_date}", "debug")
        except Exception as e:
            log(f"❌ Error parsing date '{raw_date}': {e}", "error")
            high_values.append(None)
            continue

        # Lookup instrument
        match = instruments_df[instruments_df["tradingsymbol"] == strike_name]
        if match.empty:
            log(f"⚠ No instrument found for {strike_name}", "warning")
            high_values.append(None)
            continue

        instrument_token = int(match.iloc[0]["instrument_token"])
        log(f"✔ Found instrument_token: {instrument_token}", "debug")

        # Build timestamps
        from_ts = f"{clean_date} {raw_time}"
        log(f"➡ Combined Timestamp: {from_ts}", "debug")

        try:
            dt_from = pd.to_datetime(from_ts)
        except Exception as e:
            log(f"❌ Invalid datetime '{from_ts}': {e}", "error")
            high_values.append(None)
            continue

        from_ts = dt_from.strftime("%Y-%m-%d %H:%M:%S")
        to_ts = (dt_from + timedelta(seconds=59)).strftime("%Y-%m-%d %H:%M:%S")

        log(f"✔ Final FROM: {from_ts}", "debug")
        log(f"✔ Final TO:   {to_ts}", "debug")

        # Historical API
        api_url = f"https://api.kite.trade/instruments/historical/{instrument_token}/{interval}"
        params = {"from": from_ts, "to": to_ts, "continuous": 0, "oi": 0}

        log(f"🌍 API URL: {api_url}", "debug")
        log(f"📨 Params: {params}", "debug")

        try:
            resp = requests.get(api_url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

            candles = data.get("data", {}).get("candles", [])
            if candles:
                ts, o, h, l, c, v = candles[0]
                high_values.append(h)
                log(f"✅ High={h} at {ts}")
            else:
                log("⚠ No candles returned", "warning")
                high_values.append(None)

        except Exception as e:
            log(f"❌ API Error: {e}", "error")
            log(traceback.format_exc(), "error")
            high_values.append(None)

    # Step 7: Save output
    st_df["HIGH"] = high_values
    st_df.to_excel(output_excel, index=False)
    log(f"\n✅ Results saved to {output_excel}")

except Exception as e:
    log(f"\n❌ Fatal Script Error: {e}", "error")
    log(traceback.format_exc(), "error")

finally:
    if os.path.exists(instrument_csv):
        os.remove(instrument_csv)
        log(f"🗑 Deleted {instrument_csv}")

    log("\n================ SCRIPT FINISHED ================\n")
