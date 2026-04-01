"""CSE listing data extractor — Playwright implementation.

Downloads the XLSX export from https://thecse.com/listing/listed-companies/
by clicking the JavaScript-rendered "Export List" button.

Playwright replaces the previous Selenium + undetected-chromedriver + xvfbwrapper
stack, providing:
  - Native async download interception (no filesystem polling loop)
  - Built-in auto-wait for elements (no explicit WebDriverWait boilerplate)
  - No Xvfb / virtual display needed in Docker
  - Single pip dependency instead of three

Expected XLSX columns (header on row index 2):
  Company, Symbol, Industry, Indices, Currency, Trading, Tier
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

CSE_URL = "https://thecse.com/listing/listed-companies/"
DOWNLOAD_DIR = Path(os.getenv("CSE_DOWNLOAD_DIR", "/opt/airflow/data/cse/downloads"))

# Selectors for the export UI — ordered most-specific first
_EXPORT_BUTTON_SELECTORS = [
    "button:has-text('Export List')",
    "button[id^='headlessui-menu-button']",
    "button:has(span:text('Export'))",
]

_XLSX_LINK_SELECTORS = [
    "a[href*='export-listings/xlsx']",
    "[role='menu'] a:has-text('XLSX')",
    "[role='menu'] a:has-text('Excel')",
    "[role='menuitem']:has-text('XLSX')",
]


def _parse_xlsx(xlsx_path: Path) -> list[dict]:
    """Parse the downloaded XLSX and return a list of listing dicts."""
    df = pd.read_excel(xlsx_path, header=2)  # Header is on row index 2 (3rd row)

    listings = []
    for _, row in df.iterrows():
        symbol = str(row.get("Symbol", "")).strip()
        name = str(row.get("Company", "")).strip()

        if not symbol or not name or symbol.lower() == "nan" or name.lower() == "nan":
            continue

        trading_date = None
        trading_raw = row.get("Trading", "")
        if pd.notna(trading_raw):
            try:
                if hasattr(trading_raw, "date"):
                    trading_date = trading_raw.date().isoformat()
                else:
                    trading_date = pd.to_datetime(str(trading_raw)).date().isoformat()
            except Exception:
                trading_date = None

        listings.append({
            "exchange": "CSE",
            "symbol": symbol,
            "name": name,
            "listing_url": f"https://thecse.com/en/listings/{symbol}",
            "scraped_at": datetime.now().isoformat(),
            "status": "listed",
            "active": True,
            "status_date": trading_date or datetime.now().date().isoformat(),
        })

    return listings


def extract_cse_listings() -> list[dict]:
    """Download and process the CSE listings XLSX.

    Returns a list of dicts with exchange/symbol/name/listing_url/etc. keys.
    Raises on failure so the Airflow task is marked as failed rather than silently
    returning an empty list.
    """
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": 1280, "height": 900},
            # Mimic a real browser user-agent to avoid basic bot detection
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()

        try:
            print(f"Loading {CSE_URL} ...")
            page.goto(CSE_URL, wait_until="networkidle", timeout=60_000)

            # --- Click the "Export List" button ---
            export_btn = None
            for selector in _EXPORT_BUTTON_SELECTORS:
                try:
                    page.wait_for_selector(selector, state="visible", timeout=15_000)
                    export_btn = page.locator(selector).first
                    print(f"Found export button via: {selector}")
                    break
                except PlaywrightTimeoutError:
                    continue

            if export_btn is None:
                raise RuntimeError(
                    "Could not locate the Export List button on the CSE page. "
                    "The page structure may have changed."
                )

            export_btn.scroll_into_view_if_needed()
            export_btn.click()
            print("Clicked Export List button")

            # --- Wait for the dropdown and click the XLSX option ---
            # Use expect_download so Playwright intercepts the file before it hits disk
            xlsx_locator = None
            for selector in _XLSX_LINK_SELECTORS:
                try:
                    page.wait_for_selector(selector, state="visible", timeout=10_000)
                    xlsx_locator = page.locator(selector).first
                    print(f"Found XLSX link via: {selector}")
                    break
                except PlaywrightTimeoutError:
                    continue

            if xlsx_locator is None:
                # Last resort: check if the export button href leads directly to XLSX
                href = page.locator("a[href*='.xlsx']").first.get_attribute("href")
                if href:
                    print(f"Found direct XLSX href: {href}")
                    with page.expect_download(timeout=60_000) as dl_info:
                        page.goto(href)
                else:
                    raise RuntimeError(
                        "Could not locate the XLSX download link in the dropdown. "
                        "The page structure may have changed."
                    )
            else:
                with page.expect_download(timeout=60_000) as dl_info:
                    xlsx_locator.click()

            download = dl_info.value
            print(f"Download started: {download.suggested_filename}")

            # Save to our download directory with a dated filename
            date_str = datetime.now().strftime("%Y%m%d")
            dest = DOWNLOAD_DIR / f"cse_listings_{date_str}.xlsx"

            # Avoid overwriting if the file already exists from an earlier run today
            counter = 1
            while dest.exists():
                dest = DOWNLOAD_DIR / f"cse_listings_{date_str}_{counter}.xlsx"
                counter += 1

            download.save_as(str(dest))
            print(f"Saved XLSX to: {dest}")

        finally:
            context.close()
            browser.close()

    listings = _parse_xlsx(dest)
    print(f"Extracted {len(listings)} CSE listings from {dest.name}")
    return listings


if __name__ == "__main__":
    print("Starting CSE listing extraction...")
    results = extract_cse_listings()
    print(f"\nFound {len(results)} listings")

    if results:
        print("\nFirst 10 listings:")
        for i, item in enumerate(results[:10], 1):
            print(f"  {i:2}. {item['symbol']:12} {item['name']}")

        out_file = Path(__file__).parent / "data" / "cse_listings.json"
        out_file.parent.mkdir(exist_ok=True)
        with open(out_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved to {out_file}")
