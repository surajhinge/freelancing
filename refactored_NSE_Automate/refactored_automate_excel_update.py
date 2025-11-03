#!/usr/bin/env python3
"""
updated_automate_excel_update_v2.py

- Overwrites existing HIGH column with fetched HIGH (employer requested).
- Leaves Sold column untouched.
- Highlights rows (green) where HIGH changed.
- Improved NSE session handshake + retries + fallback parsing.
- Enhanced option strike parsing and validation.

Usage:
    pip install requests pandas openpyxl
    python updated_automate_excel_update_v2.py
"""

import re
import time
import random
import os
import json
import logging
from datetime import datetime, date
import requests
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
from nsepython import nse_quote, nse_optionchain, nse_get_fno_quote

@dataclass
class StrikeInfo:
    """Information about a parsed option strike"""
    underlying: str  # Stock/Index name (e.g., 'SBIN', 'NIFTY')
    expiry: str     # Formatted expiry date (e.g., '25-NOV-2025')
    strike: float   # Strike price
    option_type: str  # 'CE' or 'PE'
    
    def __str__(self) -> str:
        return f"{self.underlying} {self.expiry} {self.strike} {self.option_type}"
# -------------------------
# Configuration (edit if needed)
# -------------------------

def parse_strike_name(strike_name: str) -> Optional[StrikeInfo]:
    """
    Parse an NSE option strike name into its components.
    
    Args:
        strike_name: String in format "SYMBOLDDMMMSTRIKECE"
                    e.g., "SBIN25NOV920CE" -> "SBIN 25-NOV-2025 920 CE"
    
    Returns:
        StrikeInfo object if parsing successful, None otherwise
    """
    try:
        if not strike_name:
            return None
            
        strike_name = strike_name.strip().upper()
        
        # Extract components using regex
        pattern = r'^([A-Z]+)(\d{2})([A-Z]{3})(\d{2,4})?(\d{1,5})(CE|PE)$'
        match = re.match(pattern, strike_name)
        
        if not match:
            logging.error(f"Invalid strike name format: {strike_name}")
            return None
            
        symbol, day, month, year, strike, option_type = match.groups()
        
        # Format expiry date
        try:
            day = int(day)
            if not 1 <= day <= 31:
                logging.error(f"Invalid day in strike name: {strike_name}")
                return None
        except ValueError:
            logging.error(f"Invalid day format in: {strike_name}")
            return None
            
        if year:
            if len(year) == 2:
                year = '20' + year
        else:
            year = '2025'  # Default to current year
            
        expiry = f"{day:02d}-{month}-{year}"
        
        # Parse strike price - last part of match
        try:
            strike_price = float(strike)
            if strike_price <= 0:
                logging.error(f"Invalid strike price <= 0 in: {strike_name}")
                return None
        except ValueError:
            logging.error(f"Invalid strike price format in: {strike_name}")
            return None
            
        info = StrikeInfo(symbol, expiry, strike_price, option_type)
        logging.info(f"Parsed strike info: {info}")
        return info
        
    except Exception as e:
        logging.error(f"Error parsing strike name {strike_name}: {e}")
        return None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nse_update.log'),
        logging.StreamHandler()
    ]
)

# Configuration Constants
FILE_PATH = "ST_calls new.xlsx"     # input Excel file
OUTPUT_FILE = "Updated_ST_calls.xlsx"
SYMBOL_COL = "StrikeName"           # column containing instrument name (e.g., SBIN25NOV920CE)
DATE_COL = "30 Oct 2025"           # column header with date (must match Excel exactly)
TIME_COL = "09:25 AM"              # optional time column header
SOLD_COL = "Sold"                  # DO NOT modify this column
HIGH_COL = "HIGH"                  # this column will be overwritten with fetched HIGH
STOCK_HIGH_COL = "Stock_High"      # optional: will store underlying stock intraday high

# Request Configuration
DELAY_MIN = 1.6                    # minimum delay between requests (seconds)
DELAY_MAX = 2.2                    # maximum delay to reduce rate limiting
MAX_RETRIES = 4                    # maximum retry attempts for failed requests

# Highlight fill for changed rows
HIGHLIGHT_FILL = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")

# Helper functions for NSE data fetching
def get_option_chain(symbol: str, is_index: bool = False) -> Optional[Dict]:
    """
    Get option chain data using nsepython.
    
    Args:
        symbol: Symbol name (e.g., 'SBIN', 'NIFTY')
        is_index: True if symbol is an index, False for equity
    
    Returns:
        dict: Option chain data if successful, None otherwise
    """
    try:
        return nse_optionchain(symbol)
    except Exception as e:
        logging.error(f"Error fetching option chain for {symbol}: {e}")
        return None

def get_stock_quote(symbol: str) -> Optional[Dict]:
    """
    Get stock quote using nsepython.
    
    Args:
        symbol: Stock symbol (e.g., 'SBIN')
    
    Returns:
        dict: Stock quote data if successful, None otherwise
    """
    try:
        return nse_quote(symbol)
    except Exception as e:
        logging.error(f"Error fetching stock quote for {symbol}: {e}")
        return None

def get_fno_quote(symbol: str) -> Optional[Dict]:
    """
    Get F&O quote using nsepython.
    
    Args:
        symbol: Symbol name
    
    Returns:
        dict: F&O quote data if successful, None otherwise
    """
    try:
        return nse_get_fno_quote(symbol)
    except Exception as e:
        logging.error(f"Error fetching F&O quote for {symbol}: {e}")
        return None

def find_option_high(chain_data: Dict[str, Any], strike_info: StrikeInfo) -> Optional[float]:
    """
    Find option high price from chain data matching strike info.
    
    Args:
        chain_data: Option chain response data from nsepython
        strike_info: Parsed strike info to match
        
    Returns:
        float: Option high price if found, None otherwise
    """
    if not chain_data or not strike_info or 'records' not in chain_data:
        logging.error(f"Invalid chain data format for {strike_info}")
        return None
        
    records = chain_data['records']
    data = records.get('data', [])
    if not data:
        logging.error(f"No option chain data found for {strike_info}")
        return None
        
    # Find matching strike
    for item in data:
        # Match strike price
        try:
            strike_price = float(item['strikePrice'])
            if abs(strike_price - strike_info.strike) > 0.0001:
                continue
        except (KeyError, ValueError, TypeError):
            continue
            
        # Match expiry
        expiry_date = item.get('expiryDate', '').upper()
        if not expiry_date or strike_info.expiry not in expiry_date:
            continue
            
        # Get option type data
        option_data = item.get(strike_info.option_type, {})
        if not option_data:
            continue
            
        # Extract high price (nsepython provides standardized field names)
        try:
            high = float(option_data.get('highPrice', 0))
            if high > 0:
                logging.info(f"Found option high {high} for {strike_info}")
                return high
        except (ValueError, TypeError):
            pass
            
    logging.warning(f"No matching option found for {strike_info}")
    return None


# -------------------------
# Helpers
# -------------------------
def jitter_delay():
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def jitter_delay(min_delay: float = DELAY_MIN, max_delay: float = DELAY_MAX):
    """Add a random delay between requests to prevent rate limiting."""
    time.sleep(random.uniform(min_delay, max_delay))
    
def safe_float(x: Any) -> Optional[float]:
    """Convert value to float safely, handling None and string formatting."""
    if x is None:
        return None
    try:
        return float(str(x).replace(",", "").strip())
    except (ValueError, TypeError):
        return None

def is_index_symbol(symbol: str) -> bool:
    """Check if a symbol is an NSE index."""
    symbol = (symbol or "").upper()
    return symbol.startswith(("NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTYBANK"))

def parse_timestamp(ts_val: Any) -> Optional[datetime]:
    """
    Parse various timestamp formats into a datetime object.
    
    Args:
        ts_val: Timestamp value in various formats
        
    Returns:
        datetime if parsing successful, None otherwise
    """
    if not ts_val:
        return None
        
    if isinstance(ts_val, datetime):
        return ts_val
        
    # Try numeric timestamp
    if isinstance(ts_val, (int, float)):
        try:
            if ts_val > 1e12:  # Milliseconds
                return datetime.fromtimestamp(ts_val / 1000)
            return datetime.fromtimestamp(ts_val)
        except (ValueError, OSError):
            pass
            
    # Try string formats
    ts_str = str(ts_val).strip().replace("Z", "")
    formats = [
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%d %b %Y %H:%M:%S",
        "%d-%b-%Y",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
            
    # Try pandas parsing as last resort
    try:
        return pd.to_datetime(ts_str)
    except Exception:
        return None


def is_index_symbol(instr):
    """Check if symbol is an NSE index."""
    instr = (instr or "").upper()
    return instr.startswith(("NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTYBANK"))

def process_option_data(strike_name):
    """
    Process option data for a given strike name using nsepython.
    Returns tuple(option_high, stock_high) or (None, None) on failure.
    """
    logging.info(f"Processing option: {strike_name}")
    
    strike_info = parse_strike_name(strike_name)
    if not strike_info:
        logging.error(f"Failed to parse strike name: {strike_name}")
        return None, None
        
    logging.info(f"Parsed strike info: {strike_info}")
    
    # Get option chain data using nsepython
    symbol = strike_info.underlying
    chain_data = get_option_chain(symbol)
    if not chain_data:
        logging.error(f"Failed to get option chain for {symbol}")
        return None, None
    
    # Get stock quote data using nsepython
    stock_data = get_stock_quote(symbol)
    if not stock_data:
        logging.warning(f"Failed to get stock quote for {symbol}")
        stock_data = None
    
    # Extract option high value
    option_high = find_option_high(chain_data, strike_info)
    if option_high:
        logging.info(f"Found option high {option_high} for {strike_info}")
    else:
        logging.warning(f"No option high found for {strike_info}")
    
    # Extract stock high if available
    try:
        stock_high = stock_data.get('priceInfo', {}).get('intraDayHighLow', {}).get('max')
        if stock_high:
            stock_high = float(stock_high)
            logging.info(f"Found stock high {stock_high} for {symbol}")
        else:
            stock_high = None
    except (AttributeError, ValueError, TypeError):
        stock_high = None
        logging.warning(f"Could not extract stock high for {symbol}")
    
    return option_high, stock_high


def safe_float(x):
    if x is None:
        return None
    try:
        return float(str(x).replace(",", "").strip())
    except Exception:
        return None


def parse_opt_ts(ts_val):
    """
    Parse various timestamp representations returned by NSE APIs into a datetime.
    Accepts:
      - ISO strings (with or without T)
      - common formats like "%d-%b-%Y %H:%M:%S"
      - epoch integers (seconds or milliseconds)
    Returns datetime or None.
    """
    if not ts_val:
        return None
    # if already datetime
    if isinstance(ts_val, datetime):
        return ts_val
    # numeric epoch
    try:
        if isinstance(ts_val, (int, float)):
            # heuristic: if > 1e12 assume ms
            iv = int(ts_val)
            if iv > 1_000_000_000_000:
                return datetime.fromtimestamp(iv / 1000)
            if iv > 1_000_000_000:
                return datetime.fromtimestamp(iv)
    except Exception:
        pass

    s = str(ts_val).strip()
    # drop timezone 'Z' for simpler parse (we assume local timezone if absent)
    s = s.replace("Z", "")
    # common formats to attempt
    fmts = [
        "%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
        "%d %b %Y %H:%M:%S", "%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%I:%M %p",
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f)
        except Exception:
            continue

    # ISO fallback via pandas (robust)
    try:
        return pd.to_datetime(s)
    except Exception:
        return None



        
    # Get the target values for matching
    target_strike = strike_info.strike
    target_expiry = strike_info.expiry_str
    target_type = strike_info.option_type
    
    def check_option_match(item):
        """Check if option item matches our target."""
        if not isinstance(item, dict):
            return False
            
        # Check strike price
        spv = safe_float(item.get("strikePrice"))
        if spv is None or abs(spv - target_strike) > 0.0001:
            return False
            
        # Check expiry if available
        item_exp = str(item.get("expiryDate", "")).upper()
        if item_exp and target_expiry.upper() not in item_exp:
            return False
            
        return True
        
    # Search through option list
    for item in data_list:
        if not check_option_match(item):
            continue
            
        # Found matching strike and expiry, now check CE/PE side
        if target_type == "CE":
            side = item.get("CE") or item.get("ce") or item.get("callOption")
        else:
            side = item.get("PE") or item.get("pe") or item.get("putOption")
            
        if not side:
            continue
            
        # Extract high value
        for k in ["high", "dayHigh", "highPrice", "dayHighPrice", "highPriceValue"]:
            v = safe_float(side.get(k))
            if v is not None:
                logging.info(f"Found high value {v} for {strike_info}")
                return v
                
    logging.warning(f"No matching option found for {strike_info}")
    return None

def get_stock_high(data):
    """
    Extract stock high price from NSE quote data by checking various paths.
    """
    if not data:
        return None
        
    nested_paths = [
        ("marketDeptOrderBook", "tradeInfo", "high"),
        ("ohlc", "high"),
        ("price", "dayHigh"),
        ("stats", "high"),
    ]
    
    def deep_get(obj, path):
        """Helper to safely traverse nested dict paths."""
        cur = obj
        try:
            for p in path:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(p)
            return cur
        except Exception:
            return None
            
    for path in nested_paths:
        high_val = safe_float(deep_get(data, path))
        if high_val is not None:
            logging.info(f"Found stock high {high_val} at path {'.'.join(path)}")
            return high_val

        # recursive shallow search for numeric 'high' like fields
        def shallow_search_for_high(d, depth=0):
            if depth > 2:
                return None
            if isinstance(d, dict):
                for kk, vv in d.items():
                    if isinstance(kk, str) and ("high" in kk.lower() or "dayhigh" in kk.lower()):
                        hv = safe_float(vv)
                        if hv is not None:
                            return hv
                for vv in d.values():
                    if isinstance(vv, (dict, list)):
                        res = shallow_search_for_high(vv, depth + 1)
                        if res is not None:
                            return res
            elif isinstance(d, list):
                for it in d:
                    res = shallow_search_for_high(it, depth + 1)
                    if res is not None:
                        return res
            return None

        sh = shallow_search_for_high(side)
        if sh is not None:
            return sh, None

        # fallback to lastPrice/ltp
        fallback = side.get("lastPrice") or side.get("lastTradedPrice") or side.get("ltp") or side.get("last")
        fv = safe_float(fallback)
        if fv is not None:
            return fv, None

        return None, None

    # helper: find items in list/dict where strike matches
    def find_items_with_strike(data_list):
        results = []
        if isinstance(data_list, list):
            for item in data_list:
                if not isinstance(item, dict):
                    continue
                sp = item.get("strikePrice") or item.get("strike")
                if sp is None:
                    continue
                try:
                    spv = float(sp)
                except Exception:
                    continue
                if abs(spv - float(strike)) > 0.0001:
                    continue
                results.append(item)
        return results

    # primary attempt: look through data_list
    for item in data_list:
        sp = item.get("strikePrice") or item.get("strike")
        if sp is None:
            continue
        try:
            spv = float(sp)
        except:
            continue
        if abs(spv - float(strike)) > 0.0001:
            continue

        # optional expiry match (if provided)
        if expiry:
            item_exp = str(item.get("expiryDate") or item.get("expiry") or "").upper()
            if item_exp and expiry.upper() not in item_exp:
                # don't strictly require, but prefer matching items that include expiry
                pass

        if otype == "CE":
            side = item.get("CE") or item.get("ce") or item.get("call")
        else:
            side = item.get("PE") or item.get("pe") or item.get("put")
        if not side:
            continue

        hv, _ = extract_high_from_side(side)

        # try to get timestamp from side (if present)
        ts = None
        for k in ("timestamp", "lastUpdateTime", "last_traded_time", "tradeTime", "lastTradedTime", "time"):
            if k in side and side.get(k):
                ts = side.get(k)
                break

        return hv, ts

    # if not found in primary data_list, try looser search across common containers
    # search records->data->items
    try:
        rec = chain_json.get("records") if isinstance(chain_json, dict) else None
        alt = None
        if rec and isinstance(rec, dict):
            alt = rec.get("data")
        if not alt and isinstance(chain_json.get("filtered"), dict):
            alt = chain_json.get("filtered").get("data")
        if alt:
            found = find_items_with_strike(alt)
            for item in found:
                if otype == "CE":
                    side = item.get("CE") or item.get("ce") or item.get("call")
                else:
                    side = item.get("PE") or item.get("pe") or item.get("put")
                if not side:
                    continue
                hv, _ = extract_high_from_side(side)
                ts = None
                for k in ("timestamp", "lastUpdateTime", "last_traded_time", "tradeTime", "lastTradedTime", "time"):
                    if k in side and side.get(k):
                        ts = side.get(k)
                        break
                return hv, ts
    except Exception:
        pass
    return None, None

def get_chain_data_list(chain_json):
    """Extract option chain data list from various possible JSON structures."""
    if not chain_json or not isinstance(chain_json, dict):
        return None
    
    # Try records.data first
    rec = chain_json.get("records")
    if rec and isinstance(rec, dict):
        data_list = rec.get("data")
        if data_list:
            return data_list
            
    # Try filtered.data next
    filtered = chain_json.get("filtered")
    if filtered and isinstance(filtered, dict):
        data_list = filtered.get("data")
        if data_list:
            return data_list
            
    # Finally try top-level data
    return chain_json.get("data")

def extract_option_identifier(data_list, strike_price, option_type):
    """
    Extract option identifier from data list matching strike price and option type.
    Returns None if no matching identifier found.
    """
    if not isinstance(data_list, list):
        return None
        
    for item in data_list:
        # Match strike price
        sp = item.get("strikePrice") or item.get("strike")
        try:
            spv = float(sp)
            if abs(spv - float(strike_price)) > 0.0001:
                continue
        except (ValueError, TypeError):
            continue
            
        # Get option side data
        if option_type == "CE":
            side = item.get("CE") or item.get("ce") or item.get("call")
        else:
            side = item.get("PE") or item.get("pe") or item.get("put")
            
        # Extract identifier
        if isinstance(side, dict):
            ident = side.get("identifier") or side.get("instrument") or side.get("symbol")
            if ident:
                return ident
                
    return None

def get_option_quotes(identifier):
    """Get option quotes from NSE APIs for a given identifier."""
    if not identifier:
        return None
        
    quote_urls = [
        f"{NSE_BASE}/api/quote-derivative?identifier={identifier}",
        f"{NSE_BASE}/api/quote?symbol={identifier}"
    ]
    
    for url in quote_urls:
        quote_data = nse_request(url)
        if quote_data:
            return quote_data
            
    return None

def extract_high_from_quote(quote_data):
    """Extract high price and timestamp from quote data."""
    if not isinstance(quote_data, dict):
        return None, None
        
    # Extract price section
    price_data = quote_data.get("price") or quote_data.get("data") or quote_data
    if not isinstance(price_data, dict):
        return None, None
        
    # Try direct high price fields
    for field in ("dayHigh", "high", "dayHighPrice", "highPrice"):
        high = safe_float(price_data.get(field))
        if high is not None:
            # Try to get timestamp
            ts = (price_data.get("lastUpdateTime") or 
                 price_data.get("timestamp") or 
                 quote_data.get("lastUpdateTime"))
            return high, ts
            
    # Try nested OHLC
    ohlc = price_data.get("ohlc")
    if isinstance(ohlc, dict):
        high = safe_float(ohlc.get("high"))
        if high is not None:
            ts = (price_data.get("lastUpdateTime") or 
                 price_data.get("timestamp") or 
                 quote_data.get("lastUpdateTime"))
            return high, ts
            
    return None, None


def get_stock_high(underlying):
    """
    Fetch equity quote and return day high (if available)
    """
    if not underlying:
        return None
        
    url = QUOTE_EQUITY_URL.format(symbol=underlying)
    quote_json, err = nse_request(url, underlying=underlying, timeout=10)
    if err:
        print(f"Stock quote error for {underlying}: {err}")
        return None
        
    price = quote_json.get("price") if isinstance(quote_json, dict) else {}
    if isinstance(price, dict):
        hi = price.get("dayHigh") or price.get("high") or price.get("dayHighPrice") or price.get("highPrice")
        return safe_float(hi)
    return None


def parse_excel_datetime(row_date, row_time, df_columns):
    """
    Convert excel Date and Time columns to a Python datetime if possible.
    Accepts datetime/date objects or common string formats.
    """
    if pd.isna(row_date):
        return None
    base = None
    # if pandas already converted to datetime
    if isinstance(row_date, datetime):
        base = row_date
    else:
        s = str(row_date).strip()
        for fmt in ("%d %b %Y", "%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %y", "%d-%m-%Y"):
            try:
                base = datetime.strptime(s, fmt)
                break
            except Exception:
                continue
        if base is None:
            try:
                base = pd.to_datetime(s)
            except Exception:
                base = None
    if base is None:
        return None

    # if no time column or missing time, return base as date-only datetime
    if TIME_COL not in df_columns or pd.isna(row_time):
        return base

    tstr = str(row_time).strip()
    tval = None
    for tf in ("%I:%M %p", "%H:%M", "%H:%M:%S"):
        try:
            tval = datetime.strptime(tstr, tf).time()
            break
        except Exception:
            continue
    if tval:
        return datetime.combine(base.date(), tval)
    return base


# -------------------------
# Main
# -------------------------
def run_update_cycle():
    """Main function to update option high prices in Excel."""
    logging.info(f"Starting update cycle, reading: {FILE_PATH}")
    
    if not os.path.exists(FILE_PATH):
        logging.error(f"Input file not found: {FILE_PATH}")
        return

    # Read Excel file
    df = pd.read_excel(FILE_PATH, engine="openpyxl")
    df_cols = df.columns.tolist()

    # Validate required columns
    if SYMBOL_COL not in df_cols:
        logging.error(f"Required column '{SYMBOL_COL}' not found. Available columns: {df_cols}")
        return

    # Ensure HIGH column exists (we will overwrite it)
    if HIGH_COL not in df_cols:
        logging.info(f"Creating {HIGH_COL} column")
        df[HIGH_COL] = None
        
    # Optional stock high column
    if STOCK_HIGH_COL not in df_cols:
        logging.info(f"Creating {STOCK_HIGH_COL} column")
        df[STOCK_HIGH_COL] = None

    # Process rows
    logging.info("Starting row processing")
    today = date.today()
    changed_indices = []

    for idx, row in df.iterrows():
        strike_name = str(row.get(SYMBOL_COL, "")).strip()
        if not strike_name:
            logging.warning(f"Row {idx}: Empty strike name, skipping")
            continue
            
        logging.info(f"Processing row {idx}: {strike_name}")
            
        # Process option data
        strike_info = parse_strike_name(strike_name)
        if not strike_info:
            logging.error(f"Row {idx}: Failed to parse strike name {strike_name}")
            continue
            
        # Process option data
        option_high, stock_high = process_option_data(strike_name)
        
        # Update stock high if available
        if stock_high is not None:
            logging.info(f"Row {idx}: Updating stock high to {stock_high}")
            df.at[idx, STOCK_HIGH_COL] = stock_high

        # Update option high if available
        if option_high is not None:
            prev_value = row.get(HIGH_COL)
            df.at[idx, HIGH_COL] = option_high
            
            # Check if value changed
            try:
                if pd.isna(prev_value) or abs(float(prev_value) - float(option_high)) > 0.0001:
                    changed_indices.append(idx)
                    logging.info(f"Row {idx}: HIGH changed from {prev_value} to {option_high}")
            except Exception as e:
                changed_indices.append(idx)
                logging.info(f"Row {idx}: New HIGH value {option_high} (previous was invalid)")
        else:
            logging.warning(f"Row {idx}: No valid option high found, keeping existing value")
            
        jitter_delay()

    # Save updated data
    logging.info(f"Saving updated data to {OUTPUT_FILE}")
    df.to_excel(OUTPUT_FILE, index=False, engine="openpyxl")
    logging.info(f"Data saved. {len(changed_indices)} rows were updated.")

    # Apply highlighting to changed rows
    if changed_indices:
        logging.info("Applying highlighting to changed rows")
        wb = load_workbook(OUTPUT_FILE)
        ws = wb.active
        
        # Find HIGH column index
        try:
            high_col_idx = [cell.value for cell in ws[1]].index(HIGH_COL) + 1
            logging.info(f"Found {HIGH_COL} column at index {high_col_idx}")
        except ValueError:
            high_col_idx = None
            logging.warning(f"Could not find {HIGH_COL} column for highlighting")

        # Apply highlighting
        highlight_fill = PatternFill(start_color='90EE90', 
                                   end_color='90EE90',
                                   fill_type='solid')
                                   
        for row_idx in changed_indices:
            excel_row = row_idx + 2  # pandas row 0 -> excel row 2 (header is row 1)
            if high_col_idx:
                cell = ws.cell(row=excel_row, column=high_col_idx)
                cell.fill = highlight_fill
                
        wb.save(OUTPUT_FILE)
        logging.info(f"Highlighting applied to {len(changed_indices)} rows")
        
    logging.info("Update cycle completed successfully")


if __name__ == "__main__":
    run_update_cycle()
