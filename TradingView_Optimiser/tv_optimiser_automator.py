#!/usr/bin/env python3
"""
TV Optimiser Automator
- Uses Playwright (sync) to automate "Test Watchlist in Current Parameters" runs for TradingView charts.
- Moves downloaded file(s) into per-chart folders (chart ID extracted from URL).
- Provides a simple Tkinter GUI for editing YAML config and launching runs.
- Logs runs to a CSV log and a rotating logger file.

Dependencies:
    pip install playwright pyyaml
    python -m playwright install

Usage:
    python tv_optimiser_automator.py --config config.yaml
    python tv_optimiser_automator.py --gui   # launches the GUI (reads/writes config.yaml by default)
"""

import argparse
import asyncio
import subprocess
import csv
import logging
import os
import re
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

# -----------------------
# Defaults and utilities
# -----------------------
DEFAULT_CONFIG_PATH = "config.yaml"
DEFAULT_LOG_FILENAME = "automation.log"
DEFAULT_CSV_LOG = "runs_log.csv"

logger = logging.getLogger("tv_optimiser_automator")
logger.setLevel(logging.DEBUG)
log_handler = logging.FileHandler(DEFAULT_LOG_FILENAME, encoding="utf-8")
log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)
console_h = logging.StreamHandler(sys.stdout)
console_h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console_h)


def now_iso():
    return datetime.utcnow().isoformat() + "Z"


def load_config(path: str) -> Dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        c = yaml.safe_load(f) or {}
    return c


def save_config(path: str, config: Dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)


def chart_id_from_url(url: str) -> Optional[str]:
    m = re.search(r"/chart/([^/]+)/?", url)
    return m.group(1) if m else None


def ensure_dir(p: str):
    Path(p).mkdir(parents=True, exist_ok=True)


# -----------------------
# File & download helpers
# -----------------------
def find_latest_file(folder: str, ignore_patterns: List[str] = None) -> Optional[str]:
    ignore_patterns = ignore_patterns or []
    files = [os.path.join(folder, f) for f in os.listdir(folder)]
    files = [f for f in files if os.path.isfile(f)]
    files = [f for f in files if not any(re.search(pat, os.path.basename(f)) for pat in ignore_patterns)]
    if not files:
        return None
    latest = max(files, key=lambda p: os.path.getmtime(p))
    return latest


def wait_for_new_file(old_snapshot: set, folder: str, timeout: int = 120, poll: float = 1.0) -> Optional[str]:
    """Fallback: poll filesystem for new file that is not partial (.crdownload)."""
    end = time.time() + timeout
    while time.time() < end:
        current = set(os.listdir(folder))
        added = current - old_snapshot
        # filter partials
        added = [a for a in added if not a.endswith(".crdownload")]
        if added:
            # ensure file is stable (size not changing)
            candidate = os.path.join(folder, sorted(added, key=lambda n: os.path.getmtime(os.path.join(folder, n)))[-1])
            stable_count = 0
            last_size = -1
            for _ in range(6):  # check size for ~3 seconds (6 * 0.5s)
                try:
                    sz = os.path.getsize(candidate)
                except Exception:
                    sz = -1
                if sz == last_size and sz > 0:
                    stable_count += 1
                    if stable_count >= 3:
                        return candidate
                else:
                    stable_count = 0
                last_size = sz
                time.sleep(0.5)
        time.sleep(poll)
    return None


# -----------------------
# Retry/backoff helper
# -----------------------
async def with_retries(fn, retries=3, base_delay=5, backoff=2, logger=None):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return await fn(attempt)
        except Exception as e:
            last_exc = e
            if logger:
                logger.warning(f"Attempt {attempt} failed: {e}")
            sleep_for = base_delay * (backoff ** (attempt - 1))
            await asyncio.sleep(sleep_for)
    raise last_exc


# -----------------------
# Automator core
# -----------------------
class TVAutomator:
    def __init__(self, config: Dict):
        self.config = config
        self.stop_event = threading.Event()
        self._validate_and_fill_config()
        ensure_dir(self.config["output_dir"])
        # CSV log
        self.csv_log_path = os.path.join(self.config["output_dir"], DEFAULT_CSV_LOG)
        if not os.path.exists(self.csv_log_path):
            with open(self.csv_log_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["timestamp_utc", "chart_id", "chart_link", "watchlist", "filename", "status", "error"])

    def _validate_and_fill_config(self):
        c = self.config
        c.setdefault("chart_links", [])
        c.setdefault("watchlists", [])
        c.setdefault("output_dir", os.path.abspath("tv_outputs"))
        c.setdefault("chrome_profile", None)  # path to profile (folder)
        c.setdefault("chrome_executable", None)  # optional explicit chrome exe path
        c.setdefault("downloads_dir", str(Path.home() / "Downloads"))
        c.setdefault("timeouts", {})
        to = c["timeouts"]
        to.setdefault("page_load", 30)
        to.setdefault("action", 15)
        to.setdefault("download", 180)
        c.setdefault("retries", {})
        r = c["retries"]
        r.setdefault("max_attempts", 3)
        r.setdefault("base_delay", 5)
        r.setdefault("backoff_factor", 2)
        c.setdefault("headless", False)
        c.setdefault("test_button_text", "Test Watchlist in Current Parameters")
        c.setdefault("test_button_selector", None)
        c.setdefault("watchlist_selector", None)
        c.setdefault("cdp_endpoint", None)  # if you prefer to connect to an already-running Chrome via CDP (http://localhost:9222)

    def log_run(self, chart_id, chart_link, watchlist, filename, status, error=""):
        with open(self.csv_log_path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([now_iso(), chart_id, chart_link, watchlist, filename or "", status, error])
        logger.info(f"[{status}] chart={chart_id} watchlist={watchlist} file={filename} err={error}")

    def stop(self):
        logger.info("Stop requested.")
        self.stop_event.set()
    
    async def launch_chrome_with_profile(self):
        """
        Start Chrome manually with remote debugging and attach via CDP.
        """
        cfg = self.config

        chrome_executable = cfg.get("chrome_executable")
        if not chrome_executable:
            chrome_executable = "C:/Program Files/Google/Chrome/Application/chrome.exe"
        user_data_dir = cfg.get("chrome_profile")
        # If using the default profile, switch to a temp profile to avoid lock issues
        default_profile = str(Path.home() / "AppData/Local/Google/Chrome/User Data")
        if user_data_dir is None or user_data_dir.replace('\\', '/').lower() == default_profile.replace('\\', '/').lower():
            temp_profile = os.path.join(cfg.get("output_dir", os.getcwd()), "tv_temp_profile")
            ensure_dir(temp_profile)
            user_data_dir = temp_profile
            logger.info(f"Using temporary Chrome profile directory: {user_data_dir}")
        if not user_data_dir:
            raise RuntimeError("chrome_profile must be set in config (path to Chrome user data dir).")

        # Start Chrome with remote debugging
        port = cfg.get("remote_debug_port", 9222)
        cmd = [
            chrome_executable,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
            "--start-maximized",
        ]
        logger.info(f"Starting Chrome with command: {' '.join(cmd)}")

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(3)
        # Check if Chrome started
        if proc.poll() is not None:
            err = proc.stderr.read().decode(errors="ignore")
            logger.error(f"Chrome process failed to start. Stderr: {err}")
            raise RuntimeError(f"Chrome process failed to start. See log for details.")
        else:
            logger.info("Chrome process started successfully.")

        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(f"http://localhost:{port}")
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()

        return browser, ctx, playwright, proc

    async def run_all(self):
        cfg = self.config
        charts = cfg["chart_links"]
        watchlists = cfg["watchlists"]

        # Safety: if using profile or extensions, headless must be False to load extensions properly.
        # We keep whatever user set but warn.
        if cfg["headless"]:
            logger.warning("headless=True set in config. If you rely on browser extensions or an existing UI injected element, "
                           "consider setting headless=False.")

        browser_context = None
        try:
            if cfg.get("cdp_endpoint"):
                logger.info(f"Connecting to CDP endpoint: {cfg['cdp_endpoint']}")
                async with async_playwright() as p:
                    browser = await p.chromium.connect_over_cdp(cfg["cdp_endpoint"])
                    # connect_over_cdp returns a Browser with contexts; take first context
                    contexts = browser.contexts
                    if contexts:
                        browser_context = contexts[0]
                    else:
                        # create a new context
                        browser_context = await browser.new_context(accept_downloads=True)
            else:
                # Launch a persistent context using the provided Chrome profile (user_data_dir).
                user_data_dir = cfg.get("chrome_profile")
                if not user_data_dir:
                    raise RuntimeError("chrome_profile must be set in config unless using cdp_endpoint.")
                # Make sure Chrome is not running with that profile (best effort)
                logger.info(f"Launching Chrome persistent context with profile: {user_data_dir}")
                launch_kwargs = {
                    "headless": cfg["headless"],
                    "accept_downloads": True,
                    "args": ["--start-maximized"],
                }
                if cfg.get("chrome_executable"):
                    launch_kwargs["executable_path"] = cfg["chrome_executable"]
                else:
                    # try using channel 'chrome' (system chrome)
                    launch_kwargs["channel"] = "chrome"
                # set downloads path if supported
                try:
                    launch_kwargs["downloads_path"] = cfg.get("downloads_dir")
                except Exception:
                    pass
                browser, browser_context, p, proc = await self.launch_chrome_with_profile()
                # Do NOT close browser_context, browser, proc, or p here!

            # For each chart link sequentially
            for chart_link in charts:
                if self.stop_event.is_set():
                    logger.info("Stop event set — exiting main loop.")
                    break
                chart_id = chart_id_from_url(chart_link) or "unknown"
                chart_folder = os.path.join(cfg["output_dir"], chart_id)
                ensure_dir(chart_folder)

                # Use a single page per chart (close after done)
                page = None
                try:
                    logger.info(f"Opening chart: {chart_link}")
                    page = await browser_context.new_page()
                    page.set_default_navigation_timeout(cfg["timeouts"]["page_load"] * 1000)
                    page.set_default_timeout(cfg["timeouts"]["action"] * 1000)
                    await page.goto(chart_link)
                    # optionally wait for a known TradingView selector
                    try:
                        await page.wait_for_selector("div.chart-container, div#chart, .chart", timeout=10000)
                    except PWTimeoutError:
                        # ignore, still continue
                        logger.debug("Chart container not detected (maybe different template). Proceeding anyway.")

                    # Optional: set each watchlist and run test
                    for watchlist in watchlists:
                        if self.stop_event.is_set():
                            break

                        async def attempt_run(attempt):
                            logger.info(f"Chart {chart_id}: running watchlist '{watchlist}', attempt {attempt}")
                            # 1) select watchlist (if selector or text provided)
                            if cfg.get("watchlist_selector"):
                                # user-provided CSS/XPath to open list and item
                                try:
                                    await page.click(cfg["watchlist_selector"])
                                except Exception as e:
                                    logger.debug(f"watchlist_selector click failed: {e}")
                            else:
                                # fallback: try to find watchlist by visible text on page
                                try:
                                    # open watchlist dropdown if needed
                                    # try to locate an element that contains the watchlist name
                                    locator = page.locator(f"text={watchlist}")
                                    if await locator.count() > 0:
                                        await locator.first.click()
                                        logger.debug("Clicked watchlist by text.")
                                    else:
                                        logger.debug("Watchlist text not found on page — continuing (watchlist selection may already be set).")
                                except Exception as e:
                                    logger.debug(f"Selecting watchlist by text failed: {e}")

                            # 2) Trigger the extension/Test action. Try several selectors/methods:
                            download_file_path = None
                            # snapshot downloads dir for fallback detection
                            downloads_dir = cfg.get("downloads_dir") or str(Path.home() / "Downloads")
                            old_snapshot = set(os.listdir(downloads_dir)) if os.path.exists(downloads_dir) else set()

                            # Primary attempt: use Playwright's expect_download
                            test_selector = cfg.get("test_button_selector")
                            test_text = cfg.get("test_button_text")

                            clicked = False
                            download_obj = None

                            try:
                                if test_selector:
                                    logger.debug(f"Trying test button CSS selector: {test_selector}")
                                    async with page.expect_download(timeout=cfg["timeouts"]["download"] * 1000) as exp:
                                        await page.click(test_selector)
                                    download_obj = await exp.value
                                    clicked = True
                                else:
                                    logger.debug(f"Trying test button text: {test_text}")
                                    locator = page.locator(f"text={test_text}")
                                    if await locator.count() > 0:
                                        async with page.expect_download(timeout=cfg["timeouts"]["download"] * 1000) as exp:
                                            await locator.first.click()
                                        download_obj = await exp.value
                                        clicked = True
                                    else:
                                        locator = page.locator(f"text={test_text.split()[0]}")
                                        if await locator.count() > 0:
                                            async with page.expect_download(timeout=cfg["timeouts"]["download"] * 1000) as exp:
                                                await locator.first.click()
                                            download_obj = await exp.value
                                            clicked = True
                            except PWTimeoutError as e:
                                logger.warning("expect_download timed out — will attempt filesystem fallback.")
                            except Exception as e:
                                logger.warning(f"Click via Playwright failed: {e}; will try fallback.")

                            if download_obj:
                                # Save directly to chart folder with suggested filename
                                suggested = download_obj.suggested_filename or f"tv_result_{int(time.time())}.csv"
                                dest_path = os.path.join(chart_folder, suggested)
                                await download_obj.save_as(dest_path)
                                download_file_path = dest_path
                            else:
                                # Fallback: try click without expecting download and poll downloads folder
                                try:
                                    if test_selector:
                                        logger.debug("Fallback clicking test selector (no expect_download).")
                                        await page.click(test_selector)
                                        clicked = True
                                    else:
                                        logger.debug("Fallback clicking test button by text (no expect_download).")
                                        # attempt to find any button text contains the phrase
                                        hits = page.locator(f"text={test_text}")
                                        if await hits.count() > 0:
                                            await hits.first.click()
                                            clicked = True
                                        else:
                                            # try any button containing 'Test Watchlist'
                                            hits2 = page.locator("text=Test Watchlist")
                                            if await hits2.count() > 0:
                                                await hits2.first.click()
                                                clicked = True
                                    if clicked:
                                        # Poll downloads dir
                                        logger.debug("Polling downloads dir for new file...")
                                        found = wait_for_new_file(old_snapshot, downloads_dir, timeout=cfg["timeouts"]["download"])
                                        if found:
                                            # move to chart folder
                                            dest = os.path.join(chart_folder, os.path.basename(found))
                                            shutil.move(found, dest)
                                            download_file_path = dest
                                        else:
                                            logger.warning("No download detected in downloads folder (fallback). Skipping this watchlist.")
                                            return {"status": "skipped", "reason": "No download detected"}
                                    else:
                                        logger.warning("Could not locate test trigger button to click. Skipping this watchlist.")
                                        return {"status": "skipped", "reason": "No test trigger button"}
                                except Exception as e:
                                    raise

                            # final: verify result exists and log success
                            if download_file_path and os.path.exists(download_file_path):
                                self.log_run(chart_id, chart_link, watchlist, download_file_path, "success")
                                return {"status": "success", "path": download_file_path}
                            else:
                                raise RuntimeError("Download handling finished but file not found.")
                        # run with retries & backoff
                        res = await with_retries(
                            attempt_run,
                            retries=cfg["retries"]["max_attempts"],
                            base_delay=cfg["retries"]["base_delay"],
                            backoff=cfg["retries"]["backoff_factor"],
                            logger=logger,
                        )
                    # end watchlists loop

                except Exception as e:
                    # log chart-level exception
                    logger.exception(f"Error processing chart {chart_id}: {e}")
                finally:
                    # Only close the page if it was successfully created
                    if page is not None:
                        try:
                            await page.close()
                        except Exception:
                            pass
            # end charts loop

        except Exception as e:
            logger.exception(f"Fatal automation error: {e}")
        finally:
            try:
                if browser_context:
                    await browser_context.close()
                if 'browser' in locals():
                    await browser.close()
                if 'proc' in locals():
                    proc.terminate()
                if 'p' in locals():
                    await p.stop()
            except Exception:
                pass


# -----------------------
# Minimal Tkinter GUI to edit config + run
# -----------------------
class ConfigGUI:
    def __init__(self, cfg_path=DEFAULT_CONFIG_PATH):
        self.cfg_path = cfg_path
        if os.path.exists(cfg_path):
            self.config = load_config(cfg_path)
        else:
            # default template
            self.config = {
                "chart_links": [],
                "watchlists": [],
                "output_dir": str(Path.cwd() / "tv_outputs"),
                "chrome_profile": None,
                "chrome_executable": None,
                "downloads_dir": str(Path.home() / "Downloads"),
                "timeouts": {"page_load": 30, "action": 15, "download": 180},
                "retries": {"max_attempts": 3, "base_delay": 5, "backoff_factor": 2},
                "headless": False,
                "test_button_text": "Test Watchlist in Current Parameters",
                "test_button_selector": None,
                "watchlist_selector": None,
                "cdp_endpoint": None,
            }
            save_config(cfg_path, self.config)

        self.automator = TVAutomator(self.config)
        self.thread = None

        # Build GUI
        self.root = tk.Tk()
        self.root.title("TV Optimiser Automator - Config")
        self.build_ui()
        self.refresh_lists()

    def build_ui(self):
        frame = tk.Frame(self.root, padx=8, pady=8)
        frame.pack(fill="both", expand=True)

        # Chart links
        tk.Label(frame, text="TradingView Chart Links:").grid(row=0, column=0, sticky="w")
        self.chart_listbox = tk.Listbox(frame, width=80, height=6)
        self.chart_listbox.grid(row=1, column=0, columnspan=3)
        tk.Button(frame, text="Add", command=self.add_chart).grid(row=2, column=0, sticky="w")
        tk.Button(frame, text="Edit", command=self.edit_chart).grid(row=2, column=1, sticky="w")
        tk.Button(frame, text="Remove", command=self.remove_chart).grid(row=2, column=2, sticky="w")

        # Watchlists
        tk.Label(frame, text="Watchlists (names used in TradingView):").grid(row=3, column=0, sticky="w", pady=(8,0))
        self.watch_listbox = tk.Listbox(frame, width=80, height=6)
        self.watch_listbox.grid(row=4, column=0, columnspan=3)
        tk.Button(frame, text="Add", command=self.add_watch).grid(row=5, column=0, sticky="w")
        tk.Button(frame, text="Edit", command=self.edit_watch).grid(row=5, column=1, sticky="w")
        tk.Button(frame, text="Remove", command=self.remove_watch).grid(row=5, column=2, sticky="w")

        # Paths and settings
        tk.Label(frame, text="Output Directory:").grid(row=6, column=0, sticky="w", pady=(8,0))
        self.output_entry = tk.Entry(frame, width=60)
        self.output_entry.grid(row=7, column=0, columnspan=2)
        tk.Button(frame, text="Browse", command=self.browse_output).grid(row=7, column=2)

        tk.Label(frame, text="Chrome Profile Path (user data dir):").grid(row=8, column=0, sticky="w", pady=(8,0))
        self.profile_entry = tk.Entry(frame, width=60)
        self.profile_entry.grid(row=9, column=0, columnspan=2)
        tk.Button(frame, text="Browse", command=self.browse_profile).grid(row=9, column=2)

        tk.Label(frame, text="Chrome Executable (optional):").grid(row=10, column=0, sticky="w", pady=(8,0))
        self.chrome_exe_entry = tk.Entry(frame, width=60)
        self.chrome_exe_entry.grid(row=11, column=0, columnspan=2)
        tk.Button(frame, text="Browse", command=self.browse_chrome_exe).grid(row=11, column=2)

        tk.Label(frame, text="Downloads Directory (fallback):").grid(row=12, column=0, sticky="w", pady=(8,0))
        self.downloads_entry = tk.Entry(frame, width=60)
        self.downloads_entry.grid(row=13, column=0, columnspan=2)
        tk.Button(frame, text="Browse", command=self.browse_downloads).grid(row=13, column=2)

        # Buttons and flags
        self.headless_var = tk.BooleanVar(value=self.config.get("headless", False))
        tk.Checkbutton(frame, text="Headless (not recommended with extensions)", variable=self.headless_var).grid(row=14, column=0, sticky="w", pady=(8,0))

        tk.Button(frame, text="Save Config", bg="#4CAF50", fg="white", command=self.save_config).grid(row=15, column=0, sticky="w", pady=(10,0))
        tk.Button(frame, text="Start Run", bg="#2196F3", fg="white", command=self.start_run).grid(row=15, column=1, sticky="w", pady=(10,0))
        tk.Button(frame, text="Stop Run", bg="#f44336", fg="white", command=self.stop_run).grid(row=15, column=2, sticky="w", pady=(10,0))

        # advanced text entries
        tk.Label(frame, text="Test Button Text (fallback):").grid(row=16, column=0, sticky="w", pady=(8,0))
        self.test_text_entry = tk.Entry(frame, width=60)
        self.test_text_entry.grid(row=17, column=0, columnspan=2)

        tk.Label(frame, text="Optional Test Button CSS Selector:").grid(row=18, column=0, sticky="w", pady=(8,0))
        self.test_selector_entry = tk.Entry(frame, width=60)
        self.test_selector_entry.grid(row=19, column=0, columnspan=2)

        tk.Label(frame, text="Optional Watchlist Selector (CSS/XPath):").grid(row=20, column=0, sticky="w", pady=(8,0))
        self.watch_selector_entry = tk.Entry(frame, width=60)
        self.watch_selector_entry.grid(row=21, column=0, columnspan=2)

        tk.Label(frame, text="CDP Endpoint (e.g. http://localhost:9222):").grid(row=22, column=0, sticky="w", pady=(8,0))
        self.cdp_entry = tk.Entry(frame, width=60)
        self.cdp_entry.grid(row=23, column=0, columnspan=2)

    # GUI callbacks
    def refresh_lists(self):
        self.chart_listbox.delete(0, tk.END)
        for link in self.config.get("chart_links", []):
            self.chart_listbox.insert(tk.END, link)
        self.watch_listbox.delete(0, tk.END)
        for w in self.config.get("watchlists", []):
            self.watch_listbox.insert(tk.END, w)
        self.output_entry.delete(0, tk.END)
        self.output_entry.insert(0, self.config.get("output_dir", ""))
        self.profile_entry.delete(0, tk.END)
        self.profile_entry.insert(0, self.config.get("chrome_profile") or "")
        self.chrome_exe_entry.delete(0, tk.END)
        self.chrome_exe_entry.insert(0, self.config.get("chrome_executable") or "")
        self.downloads_entry.delete(0, tk.END)
        self.downloads_entry.insert(0, self.config.get("downloads_dir", ""))
        self.headless_var.set(self.config.get("headless", False))
        self.test_text_entry.delete(0, tk.END)
        self.test_text_entry.insert(0, self.config.get("test_button_text", ""))
        self.test_selector_entry.delete(0, tk.END)
        self.test_selector_entry.insert(0, self.config.get("test_button_selector") or "")
        self.watch_selector_entry.delete(0, tk.END)
        self.watch_selector_entry.insert(0, self.config.get("watchlist_selector") or "")
        self.cdp_entry.delete(0, tk.END)
        self.cdp_entry.insert(0, self.config.get("cdp_endpoint") or "")

    def add_chart(self):
        link = simpledialog.askstring("Add Chart Link", "Enter TradingView chart link (e.g. https://www.tradingview.com/chart/abcd1234/):", parent=self.root)
        if link:
            self.config.setdefault("chart_links", []).append(link.strip())
            self.refresh_lists()

    def edit_chart(self):
        sel = self.chart_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        cur = self.config["chart_links"][idx]
        new = simpledialog.askstring("Edit Chart Link", "Edit TradingView chart link:", initialvalue=cur, parent=self.root)
        if new:
            self.config["chart_links"][idx] = new.strip()
            self.refresh_lists()

    def remove_chart(self):
        sel = self.chart_listbox.curselection()
        if not sel: return
        idx = sel[0]
        del self.config["chart_links"][idx]
        self.refresh_lists()

    def add_watch(self):
        w = simpledialog.askstring("Add Watchlist", "Enter Watchlist Name (as shown in TradingView):", parent=self.root)
        if w:
            self.config.setdefault("watchlists", []).append(w.strip())
            self.refresh_lists()

    def edit_watch(self):
        sel = self.watch_listbox.curselection()
        if not sel: return
        idx = sel[0]
        cur = self.config["watchlists"][idx]
        new = simpledialog.askstring("Edit Watchlist", "Edit watchlist name:", initialvalue=cur, parent=self.root)
        if new:
            self.config["watchlists"][idx] = new.strip()
            self.refresh_lists()

    def remove_watch(self):
        sel = self.watch_listbox.curselection()
        if not sel: return
        idx = sel[0]
        del self.config["watchlists"][idx]
        self.refresh_lists()

    def browse_output(self):
        d = filedialog.askdirectory(title="Select output directory")
        if d:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, d)

    def browse_profile(self):
        d = filedialog.askdirectory(title="Select Chrome profile directory (User Data dir)")
        if d:
            self.profile_entry.delete(0, tk.END)
            self.profile_entry.insert(0, d)

    def browse_chrome_exe(self):
        f = filedialog.askopenfilename(title="Select Chrome executable (optional)")
        if f:
            self.chrome_exe_entry.delete(0, tk.END)
            self.chrome_exe_entry.insert(0, f)

    def browse_downloads(self):
        d = filedialog.askdirectory(title="Select downloads directory")
        if d:
            self.downloads_entry.delete(0, tk.END)
            self.downloads_entry.insert(0, d)

    def save_config(self):
        # push GUI values into self.config and save
        self.config["output_dir"] = self.output_entry.get().strip()
        self.config["chrome_profile"] = self.profile_entry.get().strip() or None
        self.config["chrome_executable"] = self.chrome_exe_entry.get().strip() or None
        self.config["downloads_dir"] = self.downloads_entry.get().strip() or str(Path.home() / "Downloads")
        self.config["headless"] = bool(self.headless_var.get())
        self.config["test_button_text"] = self.test_text_entry.get().strip() or self.config.get("test_button_text")
        sel = self.test_selector_entry.get().strip()
        self.config["test_button_selector"] = sel or None
        wsel = self.watch_selector_entry.get().strip()
        self.config["watchlist_selector"] = wsel or None
        self.config["cdp_endpoint"] = self.cdp_entry.get().strip() or None

        save_config(self.cfg_path, self.config)
        messagebox.showinfo("Saved", f"Config saved to {self.cfg_path}")
        # refresh automator's config
        self.automator.config = self.config

    def start_run(self):
        # save current config then run
        self.save_config()
        if self.thread and self.thread.is_alive():
            messagebox.showwarning("Already Running", "Automation is already running.")
            return
        self.thread = threading.Thread(target=self._run_thread, daemon=True)
        self.thread.start()
        messagebox.showinfo("Started", "Automation started in background thread. Check logs for progress.")

    def _run_thread(self):
        try:
            self.automator = TVAutomator(self.config)
            self.automator.run_all()
            messagebox.showinfo("Finished", "Automation run completed (or stopped). See logs for details.")
        except Exception as e:
            logger.exception(f"Error running automation thread: {e}")
            messagebox.showerror("Error", f"Automation error: {e}")

    def stop_run(self):
        if hasattr(self, "automator"):
            self.automator.stop()
            messagebox.showinfo("Stopping", "Stop requested. Automation will stop between tasks.")

    def run(self):
        self.root.mainloop()


# -----------------------
# Command-line entry
# -----------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", "-c", default=DEFAULT_CONFIG_PATH, help="Path to YAML config file")
    ap.add_argument("--gui", action="store_true", help="Launch GUI to edit config and run")
    args = ap.parse_args()

    if args.gui:
        gui = ConfigGUI(cfg_path=args.config)
        gui.run()
        return

    config = load_config(args.config)
    automator = TVAutomator(config)
    try:
        asyncio.run(automator.run_all())
    except KeyboardInterrupt:
        logger.info("Interrupted by user — stopping.")
        automator.stop()


if __name__ == "__main__":
    main()
