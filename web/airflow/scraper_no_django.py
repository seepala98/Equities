"""A minimal scraper runner that does not rely on Django.

It fetches TSX JSON API and writes Listing rows directly to Postgres using psycopg2.
This keeps the Airflow image small and avoids installing Django.
"""
import os
import requests
import time
import psycopg2
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import re

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
                            INSERT INTO stocks_listing (exchange, symbol, name, listing_url, status, active, scraped_at)
                            VALUES (%s, %s, %s, %s, %s, %s, now())
                            ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, status = EXCLUDED.status, active = EXCLUDED.active, scraped_at = now()
                        """, (exchange, sym, inst_name, listing_url, status, True))
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
                    INSERT INTO stocks_listing (exchange, symbol, name, listing_url, status, active, status_date, scraped_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (exchange, symbol) DO UPDATE SET name = EXCLUDED.name, listing_url = EXCLUDED.listing_url, status = EXCLUDED.status, active = EXCLUDED.active, status_date = EXCLUDED.status_date, scraped_at = now()
                """, (exchange, symbol, name, listing_url, status, status not in ('delisted', 'suspended'), status_date))
            count += 1
        conn.commit()
    finally:
        if conn:
            conn.close()

    return f'Found {count} entries for {exchange} {status} (html)'
