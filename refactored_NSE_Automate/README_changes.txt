Refactored NSE Excel Auto-Updater
---------------------------------
Files included:
- refactored_automate_excel_update.py : The updated script (main)
- README_changes.txt : Description of changes and notes
- Original Excel files (unchanged) : kept for reference

Key changes made:
1. The script now ignores the old HIGH column on input and will write HIGH/Sold values
   based on option 'HIGH' fetched from NSE option-chain APIs.
2. Columns S (Sold) and T (HIGH) from the old Excel are no longer required as input.
   The script writes the HIGH value into the HIGH column and mirrors it into Sold.
3. For index options (NIFTY, BANKNIFTY, etc.) the option-chain indices endpoint is used.
4. For equity options, the option-chain equities endpoint is used. Additionally, the
   underlying stock intraday high is fetched and written to 'Stock_High' column.
5. Time filtering: If the row's Date column is today AND a Time value exists, the script
   attempts to compare the option record timestamp (if provided by the NSE JSON) and will
   only accept HIGH values recorded after the row's Date+Time. Note: NSE option-chain JSON
   may not always include per-option timestamps; in such cases the filter cannot be applied.
6. The script contains sensible retries and a delay between requests to reduce risk of blocking.
7. Update the FILE_PATH and column header constants at the top of the script if your Excel uses different headers.

Limitations & notes:
- NSE may block scripted requests if throttled. If you see HTTP 403, try running after adding a longer
  delay or run from a different IP. Consider using a proxy if needed and permitted.
- The script infers instrument names using a heuristic. If your StrikeName column uses a different
  naming convention, adjust parse_strike_name().
- The time-filtering relies on timestamp fields present in NSE JSON (e.g., 'timestamp' or 'lastUpdateTime').
  If those fields are absent, the script cannot enforce the "after this timestamp" rule for today.
- Test the script on a small subset first and verify returned HIGH values against NSE website/API.
