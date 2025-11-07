📌 Algo Trading – Upstox High Price Fetcher

This project fetches the high price of stocks using Upstox API based on:
✅ Date
✅ Time
✅ Instrument Key

Since the Upstox API does not support trading symbols, we use an instrument_key.


📁 Project Contents

high_values.py	→ Main script to fetch high price using Upstox API
Filtered_Instruments.xlsx	 → Cleaned sheet with trading_symbol + instrument_key (To get the instrument_key)
Instruments.xlsx	→ Input file → contains trading_symbol, instrument_key, date & time
log.txt	API call logs
Updated_Instruments.xlsx (Generated)	Final output with HIGH price added


✅ What This Script Does

✔ Reads stock details from Excel
✔ Builds API request based on:

instrument_key → formatted for URL

selected date

selected timestamp (HH:MM)
✔ Fetches 1-minute candle data for requested time
✔ Extracts and stores High Price in the output Excel
✔ Saves a log file



🔗 Source of Instrument Keys

Upstox provides official instruments list here:

📌 https://upstox.com/developer/api-documentation/instruments/

(We have already processed & filtered the required keys)


🛠 Requirements

✅ Python 3.8+
✅ Upstox API Access
✅ Excel File with required fields

Install required dependencies:

pip install pandas requests openpyxl



▶️ How to Run

1️⃣ Update your Excel input path inside the script
2️⃣ Update your Upstox API Key & Token (where needed)
3️⃣ Run:

python high_values.py


✅ Output Excel will be generated automatically

🧪 Example API Response (1-Min Candle)
{
  "status": "success",
  "data": {
    "candles": [
      ["2025-10-30T09:35:00+05:30",937.35,938.55,937.15,938.1,61638,0]
    ]
  }
}


Extracted value stored in Excel → High = 938.55