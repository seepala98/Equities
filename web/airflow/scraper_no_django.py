"""A minimal scraper runner that does not rely on Django.

It fetches TSX JSON API and writes Listing rows directly to Postgres using psycopg2.
This keeps the Airflow image small and avoids installing Django.
"""
import os
import requests
try:
    import psycopg2
except Exception:
    psycopg2 = None
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import re
import csv
from io import StringIO
import json

LISTING_PATH = '/en/listings/listing-with-us/listed-company-directory'

BASE_URL = 'https://www.tsx.com'


def run_scrape_letter(exchange: str, letter: str, status: str = 'listed') -> str:
    """Fetch a letter or numeric bucket and upsert into stocks_listing with given status.

    status should be one of: 'listed', 'recent', 'delisted', 'suspended'.
    """
    # For non-letter status pages (delisted/suspended), delegate to the status page scraper
    if status in ('delisted', 'suspended'):
        return run_scrape_status_page(exchange, status)

    exch_key = exchange.lower()
    json_url = f"{BASE_URL}/json/company-directory/search/{exch_key}/{letter}"
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; TSX-Scraper/1.0)', 'X-Requested-With': 'XMLHttpRequest', 'Referer': urljoin(BASE_URL, '/en/listings/listing-with-us/listed-company-directory')}
    try:
        jr = requests.get(json_url, headers=headers, timeout=30)
        jr.raise_for_status()
        data = jr.json()
    except Exception as e:
        return f'JSON request failed for {exchange} {letter}: {e}'
    conn = None
    count = 0
    if data and isinstance(data, dict) and data.get('results'):
        try:
            conn = psycopg2.connect(host=os.environ.get('POSTGRES_HOST', 'db'), dbname=os.environ.get('POSTGRES_DB', 'stockdb'), user=os.environ.get('POSTGRES_USER', 'stockuser'), password=os.environ.get('POSTGRES_PASSWORD', 'stockpass'), port=int(os.environ.get('POSTGRES_PORT', 5432)))
            cur = conn.cursor()
            for item in data.get('results', []):
                instruments = item.get('instruments') or []
                if not instruments:
                    sym = item.get('symbol')
                    name = item.get('name') or ''
                    listing_url = f"https://money.tmx.com/en/quote/{sym}/" if sym else None
                    if sym:
                        # route based on status: keep stocks_listing for listed, use dedicated tables for delisted/suspended
                        if status == 'listed':
                            cur.execute("""
                                INSERT INTO stocks_listing (exchange, symbol, name, listing_url, status, active, scraped_at)
                                VALUES (%s, %s, %s, %s, %s, %s, now())
                                ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, status = EXCLUDED.status, active = EXCLUDED.active, scraped_at = now()
                            """, (exchange, sym, name, listing_url, status, True))
                        elif status == 'delisted':
                            cur.execute("""
                                INSERT INTO stocks_delistedlisting (exchange, symbol, name, listing_url, delisted_date, scraped_at)
                                VALUES (%s, %s, %s, %s, %s, now())
                                ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, delisted_date = EXCLUDED.delisted_date, scraped_at = now()
                            """, (exchange, sym, name, listing_url, None))
                        else:
                            # suspended or other non-listed statuses -> suspended table
                            cur.execute("""
                                INSERT INTO stocks_suspendedlisting (exchange, symbol, name, listing_url, suspended_date, scraped_at)
                                VALUES (%s, %s, %s, %s, %s, now())
                                ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, suspended_date = EXCLUDED.suspended_date, scraped_at = now()
                            """, (exchange, sym, name, listing_url, None))
                        count += 1
                    continue

                for inst in instruments:
                    sym = inst.get('symbol')
                    inst_name = inst.get('name') or item.get('name')
                    listing_url = f"https://money.tmx.com/en/quote/{sym}/" if sym else None
                    if not sym:
                        continue
                    if status == 'listed':
                                        cur.execute("""
                                INSERT INTO stocks_listing (exchange, symbol, name, listing_url, status, active, asset_type, scraped_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                                ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, status = EXCLUDED.status, active = EXCLUDED.active, asset_type = EXCLUDED.asset_type, scraped_at = now()
                            """, (exchange, sym, inst_name, listing_url, status, True, 'STOCK'))
                    elif status == 'delisted':
                        cur.execute("""
                            INSERT INTO stocks_delistedlisting (exchange, symbol, name, listing_url, delisted_date, scraped_at)
                            VALUES (%s, %s, %s, %s, %s, now())
                            ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, delisted_date = EXCLUDED.delisted_date, scraped_at = now()
                        """, (exchange, sym, inst_name, listing_url, None))
                    else:
                        cur.execute("""
                            INSERT INTO stocks_suspendedlisting (exchange, symbol, name, listing_url, suspended_date, scraped_at)
                            VALUES (%s, %s, %s, %s, %s, now())
                            ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, suspended_date = EXCLUDED.suspended_date, scraped_at = now()
                        """, (exchange, sym, inst_name, listing_url, None))
                    count += 1

            conn.commit()
        finally:
            if conn:
                conn.close()

    return f'Found {count} entries for {exchange} {letter} (json)'


def run_scrape_status_page(exchange: str, status: str = 'delisted') -> str:
    """Fetch the status page results via JSON/XHR when possible, fall back to HTML parsing.

    The site exposes a JSON endpoint at /json/company-directory/<status>/<exchange> which returns
    a 'results' array. Use that first because it is stable and avoids JS rendering.
    """
    exch_key = exchange.lower()
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; TSX-Scraper/1.0)', 'Referer': urljoin(BASE_URL, LISTING_PATH)}
    session = requests.Session()

    json_url = f"{BASE_URL}/json/company-directory/{status}/{exch_key}"
    try:
        jr = session.get(json_url, headers={**headers, 'X-Requested-With': 'XMLHttpRequest'}, timeout=30)
        jr.raise_for_status()
        jdata = jr.json()
    except Exception:
        jdata = None

    # If JSON has results, insert directly into the status tables
    if jdata and isinstance(jdata, dict) and jdata.get('results'):
        conn = None
        count = 0
        try:
            conn = psycopg2.connect(host=os.environ.get('POSTGRES_HOST', 'db'), dbname=os.environ.get('POSTGRES_DB', 'stockdb'), user=os.environ.get('POSTGRES_USER', 'stockuser'), password=os.environ.get('POSTGRES_PASSWORD', 'stockpass'), port=int(os.environ.get('POSTGRES_PORT', 5432)))
            cur = conn.cursor()
            for item in jdata.get('results', []):
                instruments = item.get('instruments') or []
                if not instruments:
                    sym = item.get('symbol')
                    name = item.get('name') or ''
                    listing_url = f"https://money.tmx.com/en/quote/{sym}/" if sym else None
                    if not sym:
                        continue
                    if status == 'delisted':
                        cur.execute("""
                            INSERT INTO stocks_delistedlisting (exchange, symbol, name, listing_url, delisted_date, scraped_at)
                            VALUES (%s, %s, %s, %s, %s, now())
                            ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, delisted_date = EXCLUDED.delisted_date, scraped_at = now()
                        """, (exchange, sym, name, listing_url, None))
                    else:
                        cur.execute("""
                            INSERT INTO stocks_suspendedlisting (exchange, symbol, name, listing_url, suspended_date, scraped_at)
                            VALUES (%s, %s, %s, %s, %s, now())
                            ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, suspended_date = EXCLUDED.suspended_date, scraped_at = now()
                        """, (exchange, sym, name, listing_url, None))
                    count += 1
                    continue

                for inst in instruments:
                    sym = inst.get('symbol')
                    inst_name = inst.get('name') or item.get('name')
                    listing_url = f"https://money.tmx.com/en/quote/{sym}/" if sym else None
                    if not sym:
                        continue
                    if status == 'delisted':
                        cur.execute("""
                            INSERT INTO stocks_delistedlisting (exchange, symbol, name, listing_url, delisted_date, scraped_at)
                            VALUES (%s, %s, %s, %s, %s, now())
                            ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, delisted_date = EXCLUDED.delisted_date, scraped_at = now()
                        """, (exchange, sym, inst_name, listing_url, None))
                    else:
                        cur.execute("""
                            INSERT INTO stocks_suspendedlisting (exchange, symbol, name, listing_url, suspended_date, scraped_at)
                            VALUES (%s, %s, %s, %s, %s, now())
                            ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, suspended_date = EXCLUDED.suspended_date, scraped_at = now()
                        """, (exchange, sym, inst_name, listing_url, None))
                    count += 1

            conn.commit()
        finally:
            if conn:
                conn.close()

        return f'Found {count} entries for {exchange} {status} (json)'

    # fallback to HTML parsing if JSON is empty
    try:
        resp = session.get(urljoin(BASE_URL, LISTING_PATH), params={'exchange': exch_key, 'action': status}, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return f'Failed to fetch status page for {exchange} {status}: {e}'

    soup = BeautifulSoup(resp.text, 'lxml')
    rows = soup.select('table#tresults tbody tr') or soup.select('table tbody tr') or soup.select('.listed-company-directory__result-row')
    if not rows:
        return f'Found 0 entries for {exchange} {status} (html)'

    conn = None
    count = 0
    try:
        conn = psycopg2.connect(host=os.environ.get('POSTGRES_HOST', 'db'), dbname=os.environ.get('POSTGRES_DB', 'stockdb'), user=os.environ.get('POSTGRES_USER', 'stockuser'), password=os.environ.get('POSTGRES_PASSWORD', 'stockpass'), port=int(os.environ.get('POSTGRES_PORT', 5432)))
        cur = conn.cursor()
        for r in rows:
            a = r.select_one('a')
            if not a:
                continue
            name = a.get_text(strip=True)
            tds = r.find_all('td')
            symbol = None
            if len(tds) >= 2:
                sym_a = tds[1].select_one('a')
                if sym_a:
                    symbol = sym_a.get_text(strip=True)
                else:
                    symbol = tds[1].get_text(strip=True)
            else:
                m = re.search(r'/quote/([^/]+)/', a.get('href', ''))
                if m:
                    symbol = m.group(1).strip()
            if not symbol:
                continue
            listing_url = urljoin(BASE_URL, a['href']) if a and a.has_attr('href') else None
            status_date = None
            if len(tds) >= 3:
                date_text = tds[2].get_text(strip=True)
                if date_text:
                    try:
                        from datetime import datetime
                        dclean = date_text.replace('\u00A0', ' ').replace('.', '').replace('\u2009', ' ').strip()
                        for fmt in ('%b %d, %Y', '%B %d, %Y'):
                            try:
                                status_date = datetime.strptime(dclean, fmt).date()
                                break
                            except Exception:
                                continue
                    except Exception:
                        status_date = None

            if status == 'delisted':
                cur.execute("""
                    INSERT INTO stocks_delistedlisting (exchange, symbol, name, listing_url, delisted_date, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, now())
                    ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, delisted_date = EXCLUDED.delisted_date, scraped_at = now()
                """, (exchange, symbol, name, listing_url, status_date))
            elif status == 'suspended':
                cur.execute("""
                    INSERT INTO stocks_suspendedlisting (exchange, symbol, name, listing_url, suspended_date, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, now())
                    ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, suspended_date = EXCLUDED.suspended_date, scraped_at = now()
                """, (exchange, symbol, name, listing_url, None))
            else:
                cur.execute("""
                    INSERT INTO stocks_listing (exchange, symbol, name, listing_url, status, active, status_date, asset_type, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, status = EXCLUDED.status, active = EXCLUDED.active, status_date = EXCLUDED.status_date, asset_type = EXCLUDED.asset_type, scraped_at = now()
                """, (exchange, symbol, name, listing_url, status, status not in ('delisted', 'suspended'), status_date, 'STOCK'))
            count += 1
        conn.commit()
    finally:
        if conn:
            conn.close()

    return f'Found {count} entries for {exchange} {status} (html)'


def run_scrape_cboe(exchange: str = 'CBOE') -> str:
    """Download the CBOE listing CSV from the directory page and upsert into stocks_listing.

    The CBOE listing page exposes a downloadable CSV; this function finds the first
    CSV link on the page, downloads it, parses the CSV and inserts symbol+name rows
    into `stocks_listing` with exchange set to the provided exchange string.
    """
    page_url = 'https://www.cboe.com/ca/equities/market-activity/listing-directory/'
    session = requests.Session()
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; CBOE-Scraper/1.0)'}
    try:
        resp = session.get(page_url, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return f'Failed to fetch CBOE listing page: {e}'

    soup = BeautifulSoup(resp.text, 'lxml')
    csv_link = None
    for a in soup.select('a'):
        href = a.get('href', '')
        if not href:
            continue
        if href.lower().endswith('.csv') or '.csv' in href.lower():
            csv_link = urljoin('https://www.cboe.com', href)
            break

    # Fallback: try a relative filename that sometimes hosts the CSV
    if not csv_link:
        csv_link = urljoin(page_url, 'listing-directory.csv')

    cr = None
    try:
        cr = session.get(csv_link, headers=headers, timeout=60)
        cr.raise_for_status()
        text = cr.content.decode('utf-8', errors='replace')
        f = StringIO(text)
        reader = csv.DictReader(f)
    except Exception:
        # CSV unavailable or failed to parse — try to extract embedded JSON array from the page
        try:
            page = session.get(page_url, headers=headers, timeout=30)
            page.raise_for_status()
            pagetext = page.text
            # Look for a JSON array that contains objects with 'symbol' and 'marketcap' keys
            m = re.search(r'(\[\{[^\]]+\}\])', pagetext, flags=re.DOTALL)
            if m:
                jtxt = m.group(1)
                try:
                    arr = json.loads(jtxt)
                except Exception:
                    arr = None
            else:
                arr = None
        except Exception:
            arr = None
        if not arr:
            return f'Failed to download/parse CBOE CSV and no embedded JSON found at {page_url} (tried {csv_link})'

    conn = None
    count = 0
    try:
        conn = psycopg2.connect(host=os.environ.get('POSTGRES_HOST', 'db'), dbname=os.environ.get('POSTGRES_DB', 'stockdb'), user=os.environ.get('POSTGRES_USER', 'stockuser'), password=os.environ.get('POSTGRES_PASSWORD', 'stockpass'), port=int(os.environ.get('POSTGRES_PORT', 5432)))
        cur = conn.cursor()
        # If we parsed a CSV use the csv reader, otherwise use the extracted array `arr`
        if 'reader' in locals():
            for row in reader:
                sym = (row.get('Symbol') or row.get('symbol') or '').strip()
                name = (row.get('Name') or row.get('name') or '').strip()
                if not sym:
                    continue
                cur.execute("""
                    INSERT INTO stocks_listing (exchange, symbol, name, listing_url, status, active, asset_type, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, status = EXCLUDED.status, active = EXCLUDED.active, asset_type = EXCLUDED.asset_type, scraped_at = now()
                """, (exchange.lower(), sym, name or None, None, 'listed', True, 'STOCK'))
                count += 1
        else:
            for item in arr:
                sym = (item.get('symbol') or item.get('Symbol') or '').strip()
                name = (item.get('name') or item.get('Name') or '').strip()
                if not sym:
                    continue
                cur.execute("""
                    INSERT INTO stocks_listing (exchange, symbol, name, listing_url, status, active, asset_type, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, status = EXCLUDED.status, active = EXCLUDED.active, asset_type = EXCLUDED.asset_type, scraped_at = now()
                """, (exchange.lower(), sym, name or None, None, 'listed', True, 'STOCK'))
                count += 1
        conn.commit()
    finally:
        if conn:
            conn.close()

    return f'Found {count} entries for {exchange} (csv)'


def run_scrape_cse(exchange: str = 'CSE') -> str:
    """Fetch the CSE listed companies export and upsert company+symbol into stocks_listing.

    The CSE page exposes an export CSV; if a direct CSV link isn't found, try to
    extract an embedded JSON array or parse an HTML table with headers 'Company' and 'Symbol'.
    """
    page_url = 'https://thecse.com/listing/listed-companies/'
    session = requests.Session()
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; CSE-Scraper/1.0)'}
    try:
        resp = session.get(page_url, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return f'Failed to fetch CSE listing page: {e}'

    soup = BeautifulSoup(resp.text, 'lxml')
    csv_link = None
    # look for obvious CSV / export links
    for a in soup.select('a'):
        href = a.get('href', '')
        if not href:
            continue
        if href.lower().endswith('.csv') or 'export' in href.lower() or 'download' in href.lower():
            csv_link = urljoin('https://thecse.com', href)
            break

    arr = None
    reader = None
    if csv_link:
        try:
            cr = session.get(csv_link, headers=headers, timeout=60)
            cr.raise_for_status()
            text = cr.content.decode('utf-8', errors='replace')
            f = StringIO(text)
            reader = csv.DictReader(f)
        except Exception:
            reader = None

    # fallback: try to extract embedded JSON array like other pages
    if not reader:
        try:
            m = re.search(r'(\[\{[^\]]+\}\])', resp.text, flags=re.DOTALL)
            if m:
                import json
                try:
                    arr = json.loads(m.group(1))
                except Exception:
                    arr = None
        except Exception:
            arr = None

    # prepare table_rows early so later checks can reference it
    table_rows = []

    # fallback: try to extract embedded Apollo/GraphQL client state (window.__APOLLO_STATE__
    # or a large JS object) and traverse it for objects that contain 'symbol' and a name field.
    if not reader and not arr:
        try:
            text = resp.text

            def _extract_js_object(text, marker_candidates):
                for marker in marker_candidates:
                    idx = text.find(marker)
                    if idx == -1:
                        continue
                    # find the '=' after the marker
                    eq = text.find('=', idx)
                    if eq == -1:
                        continue
                    # find first '{' after '='
                    start = text.find('{', eq)
                    if start == -1:
                        continue
                    # balanced-brace parse
                    depth = 0
                    i = start
                    while i < len(text):
                        ch = text[i]
                        if ch == '{':
                            depth += 1
                        elif ch == '}':
                            depth -= 1
                            if depth == 0:
                                # return the substring including this closing brace
                                return text[start:i+1]
                        i += 1
                return None

            marker_candidates = ['window.__APOLLO_STATE__', '__APOLLO_STATE__', 'ROOT_QUERY', 'apolloState']
            js_obj_text = _extract_js_object(text, marker_candidates)
            if js_obj_text:
                try:
                    state = json.loads(js_obj_text)
                except Exception:
                    state = None
            else:
                state = None

            def _walk_collect(obj, out):
                if isinstance(obj, dict):
                    # direct hit
                    if 'symbol' in obj and ('company' in obj or 'name' in obj):
                        sym = (obj.get('symbol') or '').strip()
                        name = (obj.get('company') or obj.get('name') or '').strip()
                        if sym:
                            out.append({'symbol': sym, 'name': name})
                    # otherwise traverse children
                    for v in obj.values():
                        _walk_collect(v, out)
                elif isinstance(obj, list):
                    for it in obj:
                        _walk_collect(it, out)

            if state:
                found = []
                _walk_collect(state, found)
                # de-duplicate by symbol
                dedup = {}
                for it in found:
                    s = it.get('symbol')
                    if not s:
                        continue
                    if s not in dedup:
                        dedup[s] = it.get('name')
                if dedup:
                    arr = [{'symbol': k, 'name': v} for k, v in dedup.items()]
        except Exception:
            arr = None

    # fallback: parse HTML table if present
    table_rows = []
    if not reader and not arr:
        rows = soup.select('table tbody tr')
        for r in rows:
            tds = [td.get_text(strip=True) for td in r.find_all('td')]
            if len(tds) >= 2:
                table_rows.append(tds)

    conn = None
    count = 0
    try:
        conn = psycopg2.connect(host=os.environ.get('POSTGRES_HOST', 'db'), dbname=os.environ.get('POSTGRES_DB', 'stockdb'), user=os.environ.get('POSTGRES_USER', 'stockuser'), password=os.environ.get('POSTGRES_PASSWORD', 'stockpass'), port=int(os.environ.get('POSTGRES_PORT', 5432)))
        cur = conn.cursor()
        if reader:
            for row in reader:
                sym = (row.get('Symbol') or row.get('symbol') or '').strip()
                name = (row.get('Company') or row.get('Company Name') or row.get('company') or row.get('Name') or row.get('name') or '').strip()
                if not sym:
                    continue
                cur.execute("""
                    INSERT INTO stocks_listing (exchange, symbol, name, listing_url, status, active, asset_type, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, status = EXCLUDED.status, active = EXCLUDED.active, asset_type = EXCLUDED.asset_type, scraped_at = now()
                """, (exchange.lower(), sym, name or None, None, 'listed', True, 'STOCK'))
                count += 1
        elif arr:
            for item in arr:
                sym = (item.get('symbol') or item.get('Symbol') or '').strip()
                name = (item.get('name') or item.get('Name') or item.get('company') or '').strip()
                if not sym:
                    continue
                cur.execute("""
                    INSERT INTO stocks_listing (exchange, symbol, name, listing_url, status, active, asset_type, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, status = EXCLUDED.status, active = EXCLUDED.active, asset_type = EXCLUDED.asset_type, scraped_at = now()
                """, (exchange.lower(), sym, name or None, None, 'listed', True, 'STOCK'))
                count += 1
        else:
            for tds in table_rows:
                # attempt to map columns: Company, Symbol are common
                name = tds[0]
                sym = tds[1]
                if not sym:
                    continue
                cur.execute("""
                    INSERT INTO stocks_listing (exchange, symbol, name, listing_url, status, active, asset_type, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, status = EXCLUDED.status, active = EXCLUDED.active, asset_type = EXCLUDED.asset_type, scraped_at = now()
                """, (exchange.lower(), sym, name or None, None, 'listed', True, 'STOCK'))
                count += 1
        conn.commit()
    finally:
        if conn:
            conn.close()

    return f'Found {count} entries for {exchange.lower()} (cse)'


def parse_cse_listings(html_text):
    """Parse the CSE listing page HTML (or embedded JS state) and return a list of
    dicts {'symbol': ..., 'name': ...}. This is non-destructive and used for dry-runs.
    """
    out = []
    soup = BeautifulSoup(html_text, 'lxml')

    # 1) look for a simple embedded JSON array
    m = re.search(r'(\[\{[^\]]+\}\])', html_text, flags=re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group(1))
            for item in arr:
                sym = (item.get('symbol') or item.get('Symbol') or '').strip()
                name = (item.get('name') or item.get('Name') or item.get('company') or '').strip()
                if sym:
                    out.append({'symbol': sym, 'name': name})
            if out:
                return out
        except Exception:
            pass

    # 2) try to extract embedded Apollo/GraphQL client state
    def _extract_js_object(text, marker_candidates):
        for marker in marker_candidates:
            idx = text.find(marker)
            if idx == -1:
                continue
            eq = text.find('=', idx)
            if eq == -1:
                continue
            start = text.find('{', eq)
            if start == -1:
                continue
            depth = 0
            i = start
            while i < len(text):
                ch = text[i]
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        return text[start:i+1]
                i += 1
        return None

    marker_candidates = ['window.__APOLLO_STATE__', '__APOLLO_STATE__', 'ROOT_QUERY', 'apolloState']
    js_obj_text = _extract_js_object(html_text, marker_candidates)
    if js_obj_text:
        try:
            state = json.loads(js_obj_text)
        except Exception:
            state = None
        if state:
            def _walk_collect(obj):
                if isinstance(obj, dict):
                    if 'symbol' in obj and ('company' in obj or 'name' in obj):
                        sym = (obj.get('symbol') or '').strip()
                        name = (obj.get('company') or obj.get('name') or '').strip()
                        if sym:
                            out.append({'symbol': sym, 'name': name})
                    for v in obj.values():
                        _walk_collect(v)
                elif isinstance(obj, list):
                    for it in obj:
                        _walk_collect(it)

            _walk_collect(state)
            if out:
                # de-dupe
                seen = {}
                res = []
                for it in out:
                    s = it.get('symbol')
                    if not s or s in seen:
                        continue
                    seen[s] = True
                    res.append(it)
                return res

    # 3) fallback to HTML table parsing
    rows = soup.select('table tbody tr')
    for r in rows:
        tds = [td.get_text(strip=True) for td in r.find_all('td')]
        if len(tds) >= 2:
            name = tds[0]
            sym = tds[1]
            if sym:
                out.append({'symbol': sym, 'name': name})

    return out
