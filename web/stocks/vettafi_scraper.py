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
import json
import time
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Optional, Tuple
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


def _parse_market_cap(market_cap_str: str) -> Optional[int]:
    """Parse market cap string like '$3.90 Trillion' to integer USD."""
    if not market_cap_str:
        return None
    
    # Remove $ and whitespace
    clean_str = market_cap_str.strip().replace("$", "").strip()
    
    # Match number and unit
    match = re.match(r"^([\d,\.]+)\s*(Trillion|Billion|Million|K)?$", clean_str, re.IGNORECASE)
    if not match:
        return None
    
    value_str, unit = match.groups()
    value_str = value_str.replace(",", "")
    
    try:
        value = float(value_str)
    except ValueError:
        return None
    
    multipliers = {
        "trillion": 1_000_000_000_000,
        "billion": 1_000_000_000,
        "million": 1_000_000,
        "k": 1_000,
        None: 1,
    }
    
    multiplier = multipliers.get(unit.lower() if unit else None, 1)
    return int(value * multiplier)


def _parse_dividend_yield(yield_str: str) -> Optional[Decimal]:
    """Parse dividend yield like '0.58%' to Decimal."""
    if not yield_str:
        return None
    
    try:
        return Decimal(yield_str.strip().replace("%", ""))
    except (InvalidOperation, ValueError):
        return None


def _extract_json_from_script(script_text: str, var_name: str) -> Optional[Any]:
    """Extract JSON from a script variable assignment like 'const x = [...]'."""
    if not script_text:
        return None
    
    # Pattern: const var_name = '[...]'; or const var_name = [...];
    # Handle HTML-escaped quotes in the string
    patterns = [
        rf"const\s+{var_name}\s*=\s*'([^']+)'\s*;",
        rf"const\s+{var_name}\s*=\s*\"([^\"]+)\"\s*;",
        rf"const\s+{var_name}\s*=\s*(\[[\s\S]*\])\s*;",  # Direct array
        rf"const\s+{var_name}\s*=\s*(\{{[\s\S]*\}})\s*;",  # Direct object
    ]
    
    for pattern in patterns:
        match = re.search(pattern, script_text, re.DOTALL | re.IGNORECASE)
        if match:
            json_str = match.group(1)
            # Unescape HTML entities if it was a quoted string
            if "'" in match.group(0) or '"' in match.group(0):
                json_str = json_str.replace("&quot;", '"').replace("&#39;", "'").replace("&amp;", "&")
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue
    
    return None


def _extract_characteristics(soup: BeautifulSoup) -> Tuple[Optional[List[Dict]], Optional[int], Optional[int], Optional[Decimal]]:
    """Extract characteristics from embedded script JSON."""
    # Find script containing characteristics data
    for script in soup.find_all("script"):
        if script.string and "const characteristics =" in script.string:
            characteristics = _extract_json_from_script(script.string, "characteristics")
            if characteristics and isinstance(characteristics, list):
                # Parse individual values for direct fields
                num_constituents = None
                market_cap = None
                adjusted_market_cap = None
                dividend_yield = None
                
                for item in characteristics:
                    if not isinstance(item, dict):
                        continue
                    stat_name = item.get("stat_name", "").lower()
                    stat_value = item.get("stat_value")
                    
                    if stat_name == "number of constituents" and stat_value:
                        try:
                            num_constituents = int(str(stat_value).replace(",", ""))
                        except ValueError:
                            pass
                    elif stat_name == "market capitalization" and stat_value:
                        market_cap = _parse_market_cap(str(stat_value))
                    elif stat_name == "adjusted market capitalization" and stat_value:
                        adjusted_market_cap = _parse_market_cap(str(stat_value))
                    elif stat_name == "dividend yield" and stat_value:
                        dividend_yield = _parse_dividend_yield(str(stat_value))
                
                return characteristics, num_constituents, market_cap, adjusted_market_cap, dividend_yield
    
    return None, None, None, None, None


def _extract_constituents(soup: BeautifulSoup) -> Tuple[Optional[List[Dict]], Optional[date]]:
    """Extract top constituents from embedded script JSON."""
    # Find script containing constituents data
    for script in soup.find_all("script"):
        if script.string and "const constituentsJsonStr =" in script.string:
            constituents = _extract_json_from_script(script.string, "constituentsJsonStr")
            if constituents and isinstance(constituents, list):
                # Parse the as-of date from the HTML
                as_of_date = None
                # Look for "As of" followed by a date
                as_of_elements = soup.select("div.body-xs:contains('As of') + div.body-xs")
                for element in as_of_elements:
                    date_text = element.get_text(strip=True)
                    try:
                        # Try formats like "May 29, 2026"
                        as_of_date = datetime.strptime(date_text, "%b %d, %Y").date()
                        break
                    except ValueError:
                        try:
                            # Try other formats
                            as_of_date = datetime.strptime(date_text, "%Y-%m-%d").date()
                            break
                        except ValueError:
                            continue
                
                return constituents, as_of_date
    
    return None, None


def scrape_index_detail(index_page_url: str) -> Optional[Dict]:
    """
    Scrape an individual index detail page for rich metadata.
    
    Returns a dict with detail fields or None if failed.
    """
    try:
        logger.info(f"Fetching detail page: {index_page_url}")
        resp = requests.get(index_page_url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch {index_page_url}: {e}")
        return None
    
    soup = BeautifulSoup(resp.text, "lxml")
    base_url = "https://www.vettafi.com"
    detail_data = {}
    
    # Extract overview data (asset class, overview_category, family, rebalance frequency, description)
    overview_info = soup.select("div.index__info")
    if overview_info:
        # Get description
        desc_elem = overview_info[0].select_one("div.body-s.mob--m.mb--40.w-richtext")
        if desc_elem:
            detail_data["description"] = desc_elem.get_text(strip=True)
        
        # Get overview rows
        info_rows = overview_info[0].select("div.index__info__row")
        for row in info_rows:
            cells = row.select("div.index__info__cell")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                # Get value from the second cell (could be text, link, etc.)
                value_cell = cells[1]
                value_text = value_cell.get_text(strip=True)
                
                if "asset class" in label:
                    detail_data["asset_class"] = value_text
                elif "category" in label and "overview" not in label:
                    detail_data["overview_category"] = value_text
                elif "family" in label:
                    detail_data["family"] = value_text
                elif "region" in label:
                    detail_data["region"] = value_text
                elif "rebalance frequency" in label:
                    detail_data["rebalance_frequency"] = value_text
    
    # Extract ticker variants (price return, total return, net total return)
    ticker_rows = soup.select("div.index__info:has(div.index__info__row:contains('Price return')) div.index__info__row")
    for row in ticker_rows:
        cells = row.select("div.index__info__cell")
        if len(cells) >= 2:
            label = cells[0].get_text(strip=True).lower()
            value = cells[1].get_text(strip=True)
            if "price return" in label:
                detail_data["price_return_ticker"] = value
            elif "total return" in label:
                detail_data["total_return_ticker"] = value
            elif "net total return" in label:
                detail_data["net_total_return_ticker"] = value
    
    # Extract characteristics from embedded JSON
    characteristics, num_constituents, market_cap, adjusted_market_cap, dividend_yield = _extract_characteristics(soup)
    if characteristics is not None:
        detail_data["characteristics_json"] = characteristics
    if num_constituents is not None:
        detail_data["num_constituents"] = num_constituents
    if market_cap is not None:
        detail_data["market_capitalization"] = market_cap
    if adjusted_market_cap is not None:
        detail_data["adjusted_market_cap"] = adjusted_market_cap
    if dividend_yield is not None:
        detail_data["dividend_yield"] = dividend_yield
    
    # Extract top constituents from embedded JSON
    constituents, constituents_as_of_date = _extract_constituents(soup)
    if constituents is not None:
        detail_data["constituents_json"] = constituents
    if constituents_as_of_date is not None:
        detail_data["constituents_as_of_date"] = constituents_as_of_date
    
    # Extract resources (factsheet, methodology PDFs)
    resources = []
    factsheet_url = None
    methodology_url = None
    
    # Look in resources section
    resources_section = soup.select_one("#resources, div.index__resources")
    if resources_section:
        resource_links = resources_section.select("a.resource-card")
        for link in resource_links:
            href = link.get("href", "")
            text = link.get_text(strip=True).lower()
            if href:
                resource_info = {"url": href, "text": text}
                resources.append(resource_info)
                if "fact" in text and "sheet" in text:
                    factsheet_url = href
                elif "methodology" in text:
                    methodology_url = href
    
    # Also check the TOC docs section for backup links
    toc_docs = soup.select_one("div.toc__docs a.button-link")
    if toc_docs:
        href = toc_docs.get("href", "")
        text = toc_docs.get_text(strip=True)
        if href and "fact sheet" in text.lower():
            if not factsheet_url:
                factsheet_url = href
        elif href and "methodology" in text.lower():
            if not methodology_url:
                methodology_url = href
    
    if factsheet_url:
        detail_data["factsheet_url"] = factsheet_url
    if methodology_url:
        detail_data["methodology_url"] = methodology_url
    if resources:
        detail_data["resources_json"] = resources
    
    # Mark as successful
    detail_data["detail_scrape_success"] = True
    detail_data["detail_scraped_at"] = datetime.now()
    
    return detail_data


def scrape_all_index_details(indexes: List[Dict], delay: float = 0.5) -> List[Dict]:
    """
    Scrape detail pages for all indexes.
    
    Args:
        indexes: List of dicts with 'ticker' and 'index_page_url' keys
        delay: Seconds to wait between requests (default: 0.5)
    
    Returns:
        List of dicts with detail data (same order as input)
    """
    if not indexes:
        return []
    
    all_details = []
    total = len(indexes)
    
    for i, index_data in enumerate(indexes):
        ticker = index_data.get("ticker", "UNKNOWN")
        index_page_url = index_data.get("index_page_url")
        
        if not index_page_url:
            logger.warning(f"No index_page_url for ticker {ticker}")
            all_details.append({})
            continue
        
        logger.info(f"Scraping detail {i+1}/{total}: {ticker}")
        detail_data = scrape_index_detail(index_page_url)
        
        if detail_data is None:
            detail_data = {"detail_scrape_success": False}
        
        # Ensure we have the ticker for updating
        detail_data["ticker"] = ticker
        all_details.append(detail_data)
        
        # Rate limiting (except for last request)
        if i < total - 1:
            time.sleep(delay)
    
    logger.info(f"Completed scraping {total} index detail pages")
    return all_details
