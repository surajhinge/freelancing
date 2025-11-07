import pandas as pd
import requests
from datetime import datetime

excel_path = "Filtered_Instruments_test.xlsx"
output_excel = "Updated_demo_High_Values_min_test_final.xlsx"
log_file = "api_url_log_test_min_final.txt"

base_url = 'https://api.upstox.com/v3/historical-candle/{instrument_key}/minutes/1/{date}/{date}'

try:
    df = pd.read_excel(excel_path)
    df["HIGH"] = None  # Create/Reset HIGH column

    print("✅ Excel loaded successfully")
    print(f"ℹ Total Rows: {len(df)}")

    with open(log_file, "w", encoding="utf-8") as log:
        log.write(f"Log created at: {datetime.now()}\n\n")

        for index, row in df.iterrows():
            trading_symbol = str(row['trading_symbol'])
            instrument_key = str(row['instrument_key'])
            date = pd.to_datetime(row['Date']).strftime("%Y-%m-%d")
            time = row['Time']
            print(f"time: {time}")

            formatted_key = instrument_key.replace("|", "%7C")
            url = base_url.format(instrument_key=formatted_key, date=date)

            # Log URL
            log.write(f"{index + 1}. {trading_symbol} → {url}\n")

            try:
                response = requests.get(url)
                data = response.json()

                if ("data" in data and "candles" in data["data"]
                        and len(data["data"]["candles"]) > 0):
                    
                    candles = data['data']['candles']
                    time_data = [c for c in candles if f"T{time}" in c[0]]
                    print(time_data)
                    high_price = time_data[0][2]
                    print(high_price)

                    df.at[index, "HIGH"] = high_price

                    message = f"{index + 1}. ✅ {trading_symbol} | {date} | HIGH: {high_price}"
                else:
                    message = f"{index + 1}. ⚠️ No data for {trading_symbol} | {date}"

            except Exception as err:
                message = f"{index + 1}. ❌ API Error for {trading_symbol} | {date}: {err}"

            print(message)
            log.write(message + "\n")

    df.to_excel(output_excel, index=False)
    print(f"\n✅ HIGH values added and saved to: {output_excel}")
    print(f"📝 Log file saved at: {log_file}")

except Exception as e:
    print(f"❌ Script Failed: {e}")
