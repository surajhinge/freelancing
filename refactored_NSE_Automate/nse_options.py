"""
NSE options data fetching with improved parsing and validation.
"""
import re
import logging
from datetime import date, datetime
import requests

class StrikeInfo:
    """Represents a parsed option strike with validation."""
    
    MONTH_MAP = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }
    
    def __init__(self, underlying, day, month, year, strike, option_type):
        self.underlying = underlying.upper()
        self.day = int(day)
        self.month = self._parse_month(month)
        self.year = self._normalize_year(year)
        self.strike = float(strike)
        self.option_type = option_type.upper()
        self._validate()
    
    def _parse_month(self, month):
        """Convert month string (JAN/FEB etc) to 1-12."""
        month = str(month).upper()
        if month in self.MONTH_MAP:
            return self.MONTH_MAP[month]
        raise ValueError(f"Invalid month: {month}")
    
    def _normalize_year(self, year):
        """Convert 2-digit year to 4-digit (23->2023) or return as-is if 4-digit."""
        year = int(year)
        if year < 100:
            if year < 50:  # assume 00-49 means 2000-2049
                return 2000 + year
            return 1900 + year
        return year
    
    def _validate(self):
        """Validate the parsed components."""
        if not self.underlying or not re.match(r'^[A-Z]+$', self.underlying):
            raise ValueError(f"Invalid underlying: {self.underlying}")
        if not (1 <= self.day <= 31):
            raise ValueError(f"Invalid day: {self.day}")
        if not (1 <= self.month <= 12):
            raise ValueError(f"Invalid month number: {self.month}")
        if not (2000 <= self.year <= 2100):
            raise ValueError(f"Invalid year: {self.year}")
        if not (0 < self.strike < 1000000):
            raise ValueError(f"Invalid strike price: {self.strike}")
        if self.option_type not in ('CE', 'PE'):
            raise ValueError(f"Invalid option type: {self.option_type}")
    
    @property
    def expiry_date(self):
        """Get the expiry as datetime.date object."""
        return date(self.year, self.month, self.day)
    
    @property
    def expiry_str(self):
        """Get the expiry in NSE format (e.g. '25-Nov-2025')."""
        return self.expiry_date.strftime('%d-%b-%Y')
    
    def __str__(self):
        return f"{self.underlying} {self.expiry_str} {self.strike}{self.option_type}"

def parse_strike_name(name):
    """
    Parse names like SBIN25NOV920CE or NIFTY25NOV42600CE
    Returns StrikeInfo object or None if parsing fails.
    """
    if not name:
        return None
        
    s = str(name).strip().upper()
    
    # First try: Full format with 4-digit year
    # Example: SBIN25NOV2025920CE
    m = re.match(r'^([A-Z]+)(\d{1,2})([A-Z]{3})(\d{4})(\d+)(CE|PE)$', s)
    if m:
        try:
            return StrikeInfo(
                underlying=m.group(1),
                day=m.group(2),
                month=m.group(3),
                year=m.group(4),
                strike=m.group(5),
                option_type=m.group(6)
            )
        except ValueError as e:
            logging.warning(f"Error parsing {name}: {e}")
            return None
    
    # Second try: Short format without year (assume current year)
    # Example: SBIN25NOV920CE
    m = re.match(r'^([A-Z]+)(\d{1,2})([A-Z]{3})(\d+)(CE|PE)$', s)
    if m:
        try:
            # Use current year if not specified
            current_year = date.today().year
            return StrikeInfo(
                underlying=m.group(1),
                day=m.group(2),
                month=m.group(3),
                year=current_year,
                strike=m.group(4),
                option_type=m.group(5)
            )
        except ValueError as e:
            logging.warning(f"Error parsing {name}: {e}")
            return None
            
    logging.warning(f"Could not parse strike name: {name}")
    return None

def find_option_high(chain_json, strike_info):
    """Search option chain for matching strike and return high value."""
    if not isinstance(chain_json, dict) or not isinstance(strike_info, StrikeInfo):
        logging.warning(f"Invalid input to find_option_high")
        return None
        
    data_list = None
    for path in ['records.data', 'filtered.data', 'data']:
        try:
            curr = chain_json
            for key in path.split('.'):
                curr = curr.get(key, {})
            if isinstance(curr, list):
                data_list = curr
                break
        except (AttributeError, TypeError):
            continue
            
    if not data_list:
        logging.warning("No valid data list found in option chain")
        return None
        
    # Search for matching option
    for item in data_list:
        if not isinstance(item, dict):
            continue
            
        # Check strike price match
        try:
            strike_price = float(item.get('strikePrice', 0))
            if abs(strike_price - strike_info.strike) > 0.0001:
                continue
        except (ValueError, TypeError):
            continue
            
        # Check expiry match if available
        item_expiry = str(item.get('expiryDate', '')).upper()
        if item_expiry and strike_info.expiry_str.upper() not in item_expiry:
            continue
            
        # Get correct CE/PE side
        side_key = 'CE' if strike_info.option_type == 'CE' else 'PE'
        side = item.get(side_key) or item.get(side_key.lower())
        if not side or not isinstance(side, dict):
            continue
            
        # Look for high price in various fields
        for key in ['high', 'dayHigh', 'highPrice', 'dayHighPrice', 'highPriceValue']:
            try:
                value = float(side.get(key, 0))
                if value > 0:
                    logging.info(f"Found high value {value} for {strike_info}")
                    return value
            except (ValueError, TypeError):
                continue
                
    logging.warning(f"No matching option found for {strike_info}")
    return None

def get_stock_high(stock_json):
    """Extract stock high price from quote response."""
    if not isinstance(stock_json, dict):
        return None
        
    # Try common paths for high price
    paths = [
        ['priceInfo', 'high'],
        ['high'],
        ['dayHigh'],
        ['highPrice'],
        ['marketDeptOrderBook', 'tradeInfo', 'high']
    ]
    
    for path in paths:
        try:
            value = stock_json
            for key in path:
                value = value.get(key)
            if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '').isdigit()):
                return float(value)
        except (AttributeError, ValueError, TypeError):
            continue
            
    return None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)