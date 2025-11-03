#!/usr/bin/env python3
"""
refactored_automate_excel_update.py

- Overwrites existing HIGH column with fetched HIGH (employer requested).
- Leaves Sold column untouched.
- Highlights rows (green) where HIGH changed.
- Improved NSE session handshake + retries + fallback parsing.
- Enhanced strike parsing and validation.

Usage:
    pip install requests pandas openpyxl
    python refactored_automate_excel_update.py
"""

import re
import time
import random
import os
import logging
from datetime import datetime, date
import requests
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from nse_options import StrikeInfo, parse_strike_name, find_option_high, get_stock_high

# -------------------------
# Configuration
# -------------------------
FILE_PATH = "ST_calls new.xlsx"     # input Excel file
OUTPUT_FILE = "Updated_ST_calls.xlsx"
SYMBOL_COL = "StrikeName"           # column containing instrument name like SBIN25NOV920CE
DATE_COL = "30 Oct 2025"           # column header with date
TIME_COL = "09:25 AM"              # optional time column header
SOLD_COL = "Sold"                  # DO NOT modify this column
HIGH_COL = "HIGH"                  # this script WILL overwrite this column with fetched HIGH
STOCK_HIGH_COL = "Stock_High"      # optional: will write underlying stock intraday high here
DELAY_MIN = 1.6                    # min delay between requests
DELAY_MAX = 2.2                    # max delay (randomized)
MAX_RETRIES = 4

# NSE endpoints
BASE_URL = "https://www.nseindia.com"
OPT_CHAIN_EQ_URL = BASE_URL + "/api/option-chain-equities?symbol={symbol}"
OPT_CHAIN_IND_URL = BASE_URL + "/api/option-chain-indices?symbol={symbol}"
QUOTE_EQUITY_URL = BASE_URL + "/api/quote-equity?symbol={symbol}"

# Standard headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/115.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/json,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def get_stock_url(symbol):
    """Get URL for stock quote."""
    return QUOTE_EQUITY_URL.format(symbol=symbol)
    
def get_option_chain_url(symbol):
    """Get URL for option chain, tries indices first then equities."""
    if symbol in ('NIFTY', 'BANKNIFTY', 'FINNIFTY'):
        return OPT_CHAIN_IND_URL.format(symbol=symbol)
    return OPT_CHAIN_EQ_URL.format(symbol=symbol)

def nse_request(url, timeout=10, max_retries=MAX_RETRIES):
    """
    Make a request to NSE with fresh session and headers.
    Returns (response_json, error_or_None)
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    
    for attempt in range(max_retries):
        try:
            # Add jitter to delay
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            
            # Make request with fresh session
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            
            if not resp.text:
                raise ValueError("Empty response")
                
            data = resp.json()
            if not isinstance(data, dict):
                raise ValueError(f"Invalid JSON response type: {type(data)}")
                
            return data
            
        except Exception as e:
            logging.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt == max_retries - 1:
                return None, f"Max retries reached: {str(e)}"
                
    return None, "Unknown error"

def process_option(strike_name):
    """
    Process an option strike to get its high price and underlying stock high.
    Returns (option_high, stock_high) or (None, None) on failure.
    """
    logging.info(f"Processing option: {strike_name}")
    
    strike_info = parse_strike_name(strike_name)
    if not strike_info:
        logging.error(f"Failed to parse strike name: {strike_name}")
        return None, None
    
    logging.info(f"Parsed strike: {strike_info}")
    symbol = strike_info.underlying
    
    # Get option chain and stock data
    stock_url = get_stock_url(symbol)
    opt_url = get_option_chain_url(symbol)
    
    opt_chain = nse_request(opt_url)
    if not opt_chain:
        logging.error(f"Failed to get option chain for {symbol}")
        return None, None
        
    stock_json = nse_request(stock_url)
    if not stock_json:
        logging.warning(f"Failed to get stock quote for {symbol}")
    
    # Extract high values
    option_high = find_option_high(opt_chain, strike_info) if opt_chain else None
    stock_high = get_stock_high(stock_json) if stock_json else None
    
    if option_high:
        logging.info(f"Found option high {option_high} for {strike_info}")
    else:
        logging.warning(f"No option high found for {strike_info}")
        
    if stock_high:
        logging.info(f"Found stock high {stock_high} for {symbol}")
    
    return option_high, stock_high

def process_row(row, refs):
    """Process a single row from Excel. Returns tuple(should_highlight, error_if_any)."""
    strike_name = str(row.get(SYMBOL_COL, "")).strip()
    if not strike_name:
        return False, "Empty strike name"
    if pd.isna(strike_name):
        return False, "NaN strike name"
        
    logging.info(f"Processing row with strike: {strike_name}")
    
    option_high, stock_high = process_option(strike_name)
    if option_high is None:
        return False, f"No option high found for {strike_name}"
        
    # Store the values for batch update
    refs['highs'].append(option_high)
    if stock_high is not None:
        refs['stock_highs'].append(stock_high)
        
    # Check if we need to highlight (value changed)
    try:
        old_high = float(row[HIGH_COL])
        changed = abs(old_high - option_high) > 0.01
        if changed:
            logging.info(f"High changed for {strike_name}: {old_high} -> {option_high}")
        return changed, None
    except (ValueError, TypeError):
        return True, None  # Highlight new values

def main():
    """Main entry point."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('nse_update.log'),
            logging.StreamHandler()
        ]
    )
    
    if not os.path.exists(FILE_PATH):
        logging.error(f"Error: input file not found: {FILE_PATH}")
        return

    logging.info(f"Reading Excel file: {FILE_PATH}")
    df = pd.read_excel(FILE_PATH)

    # Validate required columns
    for col in (SYMBOL_COL, HIGH_COL):
        if col not in df.columns:
            logging.error(f"Required column missing: {col}")
            return

    # Process rows and collect results
    refs = {'highs': [], 'stock_highs': []}
    highlight_rows = []
    errors = []
    
    for idx, row in df.iterrows():
        highlight, error = process_row(row, refs)
        if highlight:
            highlight_rows.append(idx)
        if error:
            errors.append(f"Row {idx + 1}: {error}")

    # Update dataframe with new values
    df[HIGH_COL] = refs['highs']
    if STOCK_HIGH_COL and refs['stock_highs']:
        df[STOCK_HIGH_COL] = refs['stock_highs']

    # Save to Excel with highlighting
    logging.info(f"Writing updated data to {OUTPUT_FILE}")
    df.to_excel(OUTPUT_FILE, index=False)
    
    if highlight_rows:
        wb = load_workbook(OUTPUT_FILE)
        ws = wb.active
        highlight_fill = PatternFill(start_color='90EE90', 
                                   end_color='90EE90',
                                   fill_type='solid')
                                   
        high_col = None
        for idx, col in enumerate(ws[1], 1):
            if col.value == HIGH_COL:
                high_col = idx
                break
                
        if high_col:
            for row in highlight_rows:
                cell = ws.cell(row=row + 2, column=high_col)  # +2 for header and 1-based
                cell.fill = highlight_fill
                
        wb.save(OUTPUT_FILE)
        logging.info(f"Highlighted {len(highlight_rows)} changed values")
    
    if errors:
        logging.warning("Errors encountered:")
        for err in errors:
            logging.warning(err)
    
    logging.info("Processing complete")

if __name__ == "__main__":
    main()