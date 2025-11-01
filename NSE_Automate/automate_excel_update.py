import requests
import pandas as pd
from datetime import datetime
import openpyxl
from openpyxl.styles import PatternFill
import time
import os
import re

FILE_PATH = "ST_calls new.xlsx"
OUTPUT_FILE = "Updated_ST_calls.xlsx"
SYMBOL_COL = "StrikeName"

# Create session
session = requests.Session()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.nseindia.com",
    "Connection": "keep-alive",
}


def init_session():
    """Initialize NSE session cookies"""
    try:
        session.get("https://www.nseindia.com", headers=HEADERS, timeout=10)
    except Exception as e:
        print(f"⚠ Session init failed: {e}")


def extract_underlying(symbol):
    """Extract underlying from derivative symbol"""
    symbol = symbol.upper().replace("CE", "").replace("PE", "")
    for i, ch in enumerate(symbol):
        if ch.isdigit():
            return symbol[:i]
    return symbol


def get_option_price(symbol):
    """Fetch last traded price for an option from NSE API"""
    try:
        underlying = extract_underlying(symbol)
        url = f"https://www.nseindia.com/api/option-chain-equities?symbol={underlying}"

        res = session.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            print(f"⚠ NSE option fetch failed ({res.status_code}): {url}")
            return None

        data = res.json()
        records = data.get("records", {}).get("data", [])

        strike_match = re.search(r"(\d+)(CE|PE)$", symbol)
        if not strike_match:
            return None

        strike = int(strike_match.group(1))
        option_type = strike_match.group(2)

        for rec in records:
            if rec.get("strikePrice") == strike and rec.get(option_type):
                return rec[option_type].get("lastPrice")

        return None
    except Exception as e:
        print(f"❌ Option fetch error ({symbol}): {e}")
        return None


def get_stock_high(symbol):
    """Fetch today's high for stock"""
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        res = session.get(url, headers=HEADERS, timeout=10)

        if res.status_code != 200:
            print(f"⚠ NSE equity fetch failed ({res.status_code}): {url}")
            return None

        data = res.json()
        return data.get("priceInfo", {}).get("intraDayHigh")
    except Exception as e:
        print(f"❌ Stock high fetch error ({symbol}): {e}")
        return None


def run_update_cycle():
    print("\n🚀 Running manual update...")
    init_session()

    df = pd.read_excel(FILE_PATH)
    df.columns = [c.strip() for c in df.columns]

    sold_col = next((c for c in df.columns if c.lower() == "sold"), None)
    high_col = next((c for c in df.columns if c.lower() == "high"), None)
    update_col = next((c for c in df.columns if c.lower() == "updateon"), None)
    stock_high_col = "StockHigh"

    if not all([sold_col, high_col, update_col]):
        print("❌ Missing required column (Sold / HIGH / UpdateOn).")
        return

    if stock_high_col not in df.columns:
        df[stock_high_col] = None

    df[sold_col] = df[sold_col].fillna(0)
    new_high_rows = []

    for idx, row in df.iterrows():
        symbol = str(row[SYMBOL_COL]).strip().upper()
        if not symbol:
            continue

        underlying = extract_underlying(symbol)
        print(f"\n🔍 Processing {symbol} (Underlying: {underlying})")

        option_price = get_option_price(symbol)
        stock_high = get_stock_high(underlying)

        df.at[idx, stock_high_col] = stock_high

        if option_price is not None:
            prev_sold = row[sold_col]
            df.at[idx, high_col] = option_price
            df.at[idx, sold_col] = option_price
            df.at[idx, update_col] = datetime.now()

            if option_price > prev_sold:
                print(f"✅ NEW HIGH for {symbol}: {option_price}")
                new_high_rows.append(idx)
        else:
            print(f"⚠ No option data found for {symbol}")

        time.sleep(1.5)

    tmp_file = "temp_update.xlsx"
    df.to_excel(tmp_file, index=False)

    wb = openpyxl.load_workbook(tmp_file)
    ws = wb.active
    fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")

    for row in new_high_rows:
        for col in range(1, ws.max_column + 1):
            ws.cell(row=row + 2, column=col).fill = fill

    wb.save(OUTPUT_FILE)
    os.remove(tmp_file)

    print(f"\n✅ Excel Updated — New High Count: {len(new_high_rows)}")
    print(f"📁 Saved as: {OUTPUT_FILE}")


if __name__ == "__main__":
    run_update_cycle()
