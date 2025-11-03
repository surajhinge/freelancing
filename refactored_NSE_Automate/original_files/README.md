# 🧾 NSE Excel Auto-Updater

This Python script automatically updates **option prices** and **stock highs** for symbols listed in an Excel sheet — directly from **NSE India** APIs.

It reads a list of option symbols (like `SBIN25NOV920CE`) from an Excel file, fetches live market data from NSE, and updates the file with the **latest option last price** and **stock intra-day high**.

---

## ⚙️ Features

✅ Fetches **real-time option last traded prices (CE/PE)**  
✅ Fetches **equity stock intra-day highs**  
✅ Updates Excel sheet automatically  
✅ Highlights rows where a **new high** is achieved  
✅ Works for all **F&O equity symbols**  
✅ Uses **official NSE APIs** with session-based requests  

---

## 📁 Project Structure

```
NSE_Automate/
│
├── automate_excel_update.py   # Main Python script
├── ST_calls new.xlsx          # Input Excel file
├── Updated_ST_calls.xlsx      # Output (auto-created)
└── README.md                  # Documentation (this file)
```

---

## 🧮 Excel Format

The input Excel file must contain these columns:

| Column Name | Description |
|--------------|--------------|
| **StrikeName** | Option symbol (e.g., `SBIN25NOV920CE`) |
| **Sold** | Previously recorded price |
| **HIGH** | Latest high value (will be updated) |
| **UpdateOn** | Timestamp of the last update |

An extra column **`StockHigh`** will be added automatically if it doesn’t exist.

---

## 🚀 How It Works

1. Reads data from your Excel file (`ST_calls new.xlsx`)  
2. Extracts underlying stock names from option symbols (e.g., `SBIN` from `SBIN25NOV920CE`)  
3. Fetches:
   - **Option last traded price** → via `/api/option-chain-equities`
   - **Stock intra-day high** → via `/api/quote-equity`
4. Updates Excel with the new data  
5. Highlights rows where the new price exceeds the previous “Sold” value  

---

## 🧰 Requirements

- Python 3.8+
- Libraries:
  ```bash
  pip install requests pandas openpyxl
  ```

---

## ▶️ Usage

Run the script manually anytime you want to update the Excel file:

```bash
python automate_excel_update.py
```

The script will:
- Fetch live data
- Update your Excel file
- Save a new file: **`Updated_ST_calls.xlsx`**

Example output:

```
🚀 Running manual update...

🔍 Processing SBIN25NOV920CE (Underlying: SBIN)
✅ NEW HIGH for SBIN25NOV920CE: 14.25
Stock High for SBIN: 892.50

✅ Excel Updated — New High Count: 3
📁 Saved as: Updated_ST_calls.xlsx
```

---

## 🧠 Notes

- NSE blocks excessive requests. A short delay (`1.5 sec`) is added between each API call.  
- Make sure you have a stable internet connection.  
- You can schedule the script (e.g., via **Windows Task Scheduler** or **cron**) to run every few minutes automatically.  

---

## 🧑‍💻 Author

**Suraj Hinge**  
📬 [GitHub](https://github.com/surajhinge)
