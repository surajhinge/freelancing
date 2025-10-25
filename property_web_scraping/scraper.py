"""
Rightmove scraper (standalone)
- Paginates through results per area
- Filters to last N days via Rightmove query param (default 14)
- Supports "sale" and/or "rent" modes (set in config.json)
- Outputs CSV (and optional Excel)
- Minimal deps: requests, bs4, pandas, (openpyxl only if writing Excel)
Note: Sites change often; if selectors break, see README (Troubleshooting).
"""
import sys
import time
import json
import math
import random
import argparse
import urllib.parse
from datetime import datetime, timedelta

import requests
import pandas as pd
from bs4 import BeautifulSoup

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

REQUIRED_COLUMNS = [
    "Area/Postcode",
    "Full Address",
    "Sold/Rented Status",
    "Source Platform",
    "Google Maps Location Link",
    "Property Details Link",
]

def load_config(path="config.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_rightmove_url(area, mode, days=14, offset=0):
    """
    mode: 'sale' or 'rent'
    days: last N days since added (Rightmove supports maxDaysSinceAdded)
    offset: pagination offset, multiples of 24 (Rightmove shows 24 per page)
    """
    # Core parameters
    params = {
        "locationIdentifier": f"OUTCODE^{area}",
        "includeSSTC": "true",      # show Sold STC for sale
        "includeLetAgreed": "true", # show Let Agreed for rent (RM may honor)
        "sortType": "6",            # 'Newest listed'
        "maxDaysSinceAdded": str(days),
        "propertyTypes": "",
        "mustHave": "",
        "dontShow": "",
        "furnishTypes": "",
        "keywords": "",
    }
    # Pagination param differs by layout; commonly "index"
    if offset:
        params["index"] = str(offset)

    if mode == "sale":
        # for-sale endpoint
        base = "https://www.rightmove.co.uk/property-for-sale/find.html"
    elif mode == "rent":
        # to-rent endpoint
        base = "https://www.rightmove.co.uk/property-to-rent/find.html"
    else:
        raise ValueError("mode must be 'sale' or 'rent'")
    return base + "?" + urllib.parse.urlencode(params, doseq=True)

def get_soup(url, retries=3, timeout=20, sleep_between=(2, 5), user_agent=DEFAULT_UA):
    last_exc = None
    headers = {"User-Agent": user_agent, "Accept-Language": "en-GB,en;q=0.9"}
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200 and resp.text:
                return BeautifulSoup(resp.text, "html.parser")
            else:
                last_exc = RuntimeError(f"HTTP {resp.status_code}")
        except Exception as e:
            last_exc = e
        # backoff
        time.sleep(random.uniform(*sleep_between) * attempt)
    if last_exc:
        raise last_exc
    return None

def parse_cards(soup):
    """
    Return list of dict property rows from a results page soup.
    Tries several selectors for resilience.
    """
    results = []

    # Try common container selectors
    containers = []
    # Legacy cards
    containers.extend(soup.select("div.l-searchResult.is-list"))
    # Newer card structure (as of 2024-2025 often uses li[data-test='propertyCard'] etc.)
    containers.extend(soup.select("li[data-test='propertyCard']"))
    containers.extend(soup.select("div.propertyCard"))

    seen = set()
    for card in containers:
        try:
            # Details link
            a = (card.select_one("a.propertyCard-link") or
                 card.select_one("a[data-test='property-details']") or
                 card.select_one("a[href*='/properties/']"))
            if not a or not a.get("href"):
                continue
            href = a.get("href")
            if href.startswith("/"):
                details_link = "https://www.rightmove.co.uk" + href
            else:
                details_link = href

            if details_link in seen:
                continue
            seen.add(details_link)

            # Address
            address_el = (card.select_one("address.propertyCard-address") or
                          card.select_one("[data-test='property-description'] address") or
                          card.select_one("address") or
                          card.select_one("[itemprop='address']"))
            address = address_el.get_text(strip=True) if address_el else "N/A"

            # Status (Added/Reduced/SSTC/Let Agreed)
            status_el = (card.select_one(".propertyCard-branchSummaryAddedOrReduced") or
                         card.select_one("[data-test='added-or-reduced']") or
                         card.select_one(".property-information") or
                         card.select_one("[data-test='status']"))
            status = status_el.get_text(" ", strip=True) if status_el else "Available"

            row = {
                "Full Address": address,
                "Sold/Rented Status": status,
                "Property Details Link": details_link,
            }
            results.append(row)
        except Exception:
            continue
    return results

def within_last_n_days(status_text, n_days=14):
    """
    Heuristic: extract date phrases like 'Added on 12 Aug 2025' or 'Reduced on...'
    If no date present, return True (let the maxDaysSinceAdded param do the filtering).
    """
    if not status_text:
        return True
    text = status_text.lower()

    # Quick pass: if RM already filtered by maxDaysSinceAdded, accept
    # But we still try to parse to be safe.
    # Patterns like 'added on 12 aug 2025' or 'reduced on 5 jul 2025'
    import re
    m = re.search(r"(added|reduced)\s+on\s+(\d{1,2}\s+[a-z]{3,9}\s+\d{4})", text)
    if m:
        try:
            dt = datetime.strptime(m.group(2), "%d %b %Y")
            return (datetime.now() - dt).days <= n_days
        except Exception:
            pass
    # Patterns like 'new this week' / 'added today' / 'yesterday'
    if any(kw in text for kw in ["today", "yesterday", "new this week", "this week"]):
        return True
    return True  # default true; server-level filter should have done it

def scrape_area(area, mode, days, max_pages, sleep_between):
    """
    Scrape multiple pages for an area & mode.
    Returns list of rows with required columns filled.
    """
    rows = []
    for page in range(max_pages):
        offset = page * 24  # RM shows 24 cards per page
        url = build_rightmove_url(area, mode, days=days, offset=offset)
        print(f"[{mode.upper()}] {area} | page {page+1} -> {url}")
        try:
            soup = get_soup(url, sleep_between=sleep_between)
        except Exception as e:
            print(f"  ! Failed to fetch page {page+1} for {area} ({mode}): {e}")
            break

        cards = parse_cards(soup)
        if not cards:
            print("  • No more results on this page. Stopping pagination.")
            break

        for c in cards:
            status_ok = within_last_n_days(c.get("Sold/Rented Status", ""), n_days=days)
            if not status_ok:
                continue

            address = c.get("Full Address", "N/A") or "N/A"
            maps_link = "https://www.google.com/maps/search/" + urllib.parse.quote(address)

            rows.append({
                "Area/Postcode": area,
                "Full Address": address,
                "Sold/Rented Status": c.get("Sold/Rented Status", "Available"),
                "Source Platform": "Rightmove",
                "Google Maps Location Link": maps_link,
                "Property Details Link": c.get("Property Details Link", ""),
            })

        # polite crawling
        time.sleep(random.uniform(*sleep_between))

    return rows

def main():
    parser = argparse.ArgumentParser(description="Rightmove scraper (14-day filter, pagination).")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--excel", action="store_true", help="Also save Excel (.xlsx)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    areas = cfg.get("areas", [])
    modes = cfg.get("modes", ["sale"])  # 'sale', 'rent'
    days = int(cfg.get("days_since_added", 14))
    max_pages = int(cfg.get("max_pages_per_area", 5))
    sleep_between = tuple(cfg.get("sleep_between_seconds", [2, 5]))
    output_csv = cfg.get("output_csv", "properties.csv")
    output_xlsx = cfg.get("output_xlsx", "properties.xlsx")

    if not areas:
        print("No areas configured. Add postcodes to config.json -> 'areas'.")
        sys.exit(1)

    all_rows = []
    for area in areas:
        for mode in modes:
            try:
                area_rows = scrape_area(area, mode, days, max_pages, sleep_between)
                all_rows.extend(area_rows)
            except Exception as e:
                print(f"Error scraping {area} ({mode}): {e}")

    if not all_rows:
        print("No data collected. Exiting.")
        sys.exit(2)

    # Create DataFrame with stable column order
    df = pd.DataFrame(all_rows)
    # Ensure all required columns exist
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[REQUIRED_COLUMNS]

    # Drop duplicates by details link
    if "Property Details Link" in df.columns:
        df = df.drop_duplicates(subset=["Property Details Link"], keep="first")

    # Save CSV
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"✅ CSV saved: {output_csv} ({len(df)} rows)")

    # Optionally save Excel
    if args.excel:
        try:
            df.to_excel(output_xlsx, index=False)
            print(f"✅ Excel saved: {output_xlsx}")
        except Exception as e:
            print(f"⚠️ Could not save Excel. Install 'openpyxl' if needed. Error: {e}")

if __name__ == "__main__":
    main()