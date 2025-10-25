Property Scraper (Rightmove) — 14-Day Filter

This is a self-contained Python scraper that collects **properties added in the last 14 days** from **Rightmove** for your specified **postcodes/areas** and saves them to **CSV** (and optionally **Excel**). It supports **for-sale** and **to-rent** modes and paginates through multiple result pages.

> ⚠️ Portals change their HTML frequently. If you notice missing results, see **Troubleshooting** below to adjust selectors.

---

## What it captures
- Area/Postcode  
- Full Address  
- Sold/Rented Status (e.g., *Added on*, *Reduced on*, *SSTC*, *Let Agreed*)  
- Source Platform (Rightmove)  
- Google Maps Location Link  
- Property Details Link  

---

## Quick Start

### 1) Install Python
- Windows/Mac: Install **Python 3.9+** from https://www.python.org/downloads/
- During Windows install, check **"Add Python to PATH"**.

### 2) Download this folder
- Files:
  - `scraper.py`
  - `config.json`
  - `requirements.txt`
  - `README.md` (this file)

### 3) Install dependencies
Open **Terminal** (Mac) or **Command Prompt / PowerShell** (Windows) in this folder and run:
```bash
pip install -r requirements.txt