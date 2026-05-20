"""
VettaFi Index Finder Scraper
============================

Scrapes all indexes from VettaFi category pages.
Each category page lists indexes with ticker, name, category, sub-category, region,
factsheet URL, and methodology URL.

Categories:
- equity_benchmark: https://www.vettafi.com/indexing/category/equity-benchmark
- fixed_income_benchmark: https://www.vettafi.com/indexing/category/fixed-income-benchmark
- factor: https://www.vettafi.com/indexing/category/factor
- thematic: https://www.vettafi.com/indexing/category/thematic
- custom_equity: https://www.vettafi.com/indexing/category/custom-equity
- assets: https://www.vettafi.com/indexing/category/assets
- derivatives: https://www.vettafi.com/indexing/category/derivatives
- strategy: https://www.vettafi.com/indexing/category/strategy1
"""

import re
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.vettafi.com"

CATEGORIES = {
    "equity_benchmark": "/indexing/category/equity-benchmark",
    "fixed_income_benchmark": "/indexing/category/fixed-income-benchmark",
    "factor": "/indexing/category/factor",
    "thematic": "/indexing/category/thematic",
    "custom_equity": "/indexing/category/custom-equity",
    "assets": "/indexing/category/assets",
    "derivatives": "/indexing/category/derivatives",
    "strategy": "/indexing/category/strategy1",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

REGION_MAP = {
    "north america": "north_america",
    "emea": "emea",
    "asia-pacific": "asia_pacific",
    "latin america": "latin_america",
    "global": "global",
    "japan": "japan",
    "global (ex-us)": "global_ex_us",
    "developed": "developed",
    "developed (ex-us)": "developed_ex_us",
    "emerging markets": "emerging_markets",
    "americas": "americas",
}


def _normalize_region(region_text: str) -> Optional[str]:
    """Normalize region text to database choice key."""
    if not region_text:
        return None
    cleaned = region_text.strip().lower()
    return REGION_MAP.get(cleaned, "other")


def _parse_index_row(row_div, category: str) -> Optional[Dict]:
    """Parse a single index row (div.data-table__row.w-dyn-item)."""
    ticker_a = row_div.select_one('a[href*="/indexing/index/"]')
    if not ticker_a:
        return None

    ticker = ticker_a.get_text(strip=True).upper()
    if not ticker or len(ticker) > 32:
        return None

    index_url = ticker_a.get("href", "")
    if index_url.startswith("/"):
        index_url = f"{BASE_URL}{index_url}"

    name_el = row_div.select_one(".body-s.hover-medium, .body-s.is--category.hover-medium")
    if not name_el:
        cells = row_div.select(".data-table__cell")
        if len(cells) >= 2:
            name_el = cells[1].select_one(".body-s")
    name = name_el.get_text(strip=True) if name_el else ticker

    category_el = row_div.select_one(".body-s.is--category")
    sub_category = category_el.get_text(strip=True) if category_el else ""

    region = ""
    hidden_el = row_div.select_one(".data-table__hidden-filters")
    if hidden_el:
        region = hidden_el.get_text(strip=True)

    factsheet_url = None
    methodology_url = None

    links = row_div.select("a.data-table__link__link")
    for link in links:
        href = link.get("href", "")
        link_text = link.get_text(strip=True).lower()
        if "fact" in link_text and "sheet" in link_text:
            factsheet_url = href if href.startswith("http") else urljoin(BASE_URL, href)
        elif "methodology" in link_text:
            methodology_url = href if href.startswith("http") else urljoin(BASE_URL, href)

    if not name:
        name = ticker

    return {
        "ticker": ticker,
        "name": name,
        "sub_category": sub_category,
        "region": _normalize_region(region),
        "factsheet_url": factsheet_url,
        "methodology_url": methodology_url,
        "index_page_url": index_url,
    }


def _get_next_page_url(html: str, current_url: str) -> Optional[str]:
    """Extract next page URL from pagination."""
    soup = BeautifulSoup(html, "lxml")

    # Find the next page link: <a class="w-pagination-next" href="?..._page=2">
    next_a = soup.select_one('a.w-pagination-next[href*="_page="]')
    if next_a:
        href = next_a.get("href", "")
        if href and href != "#":
            if href.startswith("http"):
                return href
            elif href.startswith("/"):
                return f"{BASE_URL}{href}"
            else:
                parsed = urlparse(current_url)
                base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                return f"{base}{href}"

    # Fallback: check prerender link
    prerender = soup.select_one('link[rel="prerender"][href*="_page="]')
    if prerender:
        href = prerender.get("href", "")
        if href and href != "#":
            if href.startswith("http"):
                return href
            elif href.startswith("/"):
                return f"{BASE_URL}{href}"
            else:
                parsed = urlparse(current_url)
                base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                return f"{base}{href}"

    return None


def scrape_category_page(category: str, max_pages: int = 50) -> List[Dict]:
    """
    Scrape all indexes from a VettaFi category page.
    """
    if category not in CATEGORIES:
        raise ValueError(f"Unknown category: {category}. Choose from: {list(CATEGORIES.keys())}")

    url = f"{BASE_URL}{CATEGORIES[category]}"
    all_indexes = []
    seen_tickers = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    for page_num in range(max_pages):
        try:
            logger.info(f"Fetching {category} page {page_num + 1}: {url}")
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            break

        soup = BeautifulSoup(resp.text, "lxml")

        rows = soup.select(".data-table__row.w-dyn-item")
        if not rows:
            logger.info(f"No rows found on {category} page {page_num + 1}")
            break

        page_count = 0
        for row in rows:
            parsed = _parse_index_row(row, category)
            if parsed and parsed["ticker"] not in seen_tickers:
                parsed["category"] = category
                all_indexes.append(parsed)
                seen_tickers.add(parsed["ticker"])
                page_count += 1

        logger.info(f"Found {page_count} new indexes on {category} page {page_num + 1} (total: {len(all_indexes)})")

        next_url = _get_next_page_url(resp.text, url)
        if not next_url:
            logger.info(f"No next page found for {category}")
            break
        url = next_url

    logger.info(f"Total indexes scraped from {category}: {len(all_indexes)}")
    return all_indexes


def scrape_all_categories(max_pages_per_category: int = 50) -> List[Dict]:
    """
    Scrape all indexes from all VettaFi categories.
    """
    all_indexes = []
    seen_tickers = set()

    for category in CATEGORIES:
        try:
            indexes = scrape_category_page(category, max_pages_per_category)
            for idx in indexes:
                if idx["ticker"] not in seen_tickers:
                    all_indexes.append(idx)
                    seen_tickers.add(idx["ticker"])
        except Exception as e:
            logger.error(f"Failed to scrape category {category}: {e}")

    logger.info(f"Total unique indexes scraped: {len(all_indexes)}")
    return all_indexes
