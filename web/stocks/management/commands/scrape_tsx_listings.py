from django.core.management.base import BaseCommand
from stocks.models import Listing, DelistedListing, SuspendedListing
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import re

BASE_URL = 'https://www.tsx.com'
LISTING_PATH = '/en/listings/listing-with-us/listed-company-directory'


class Command(BaseCommand):
    help = 'Scrape TSX and TSXV listings and store them in Listing model.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exchange',
            choices=['TSX', 'TSXV', 'both'],
            default='both',
            help='Which exchange to scrape',
        )

        parser.add_argument(
            '--letters',
            nargs='*',
            help='Letters or numbers to fetch (e.g. A B C 0-9). If omitted, will iterate A-Z and 0-9',
        )

        parser.add_argument(
            '--status',
            choices=['listed', 'delisted', 'suspended'],
            default='listed',
            help='Which listing status to fetch (listed/delisted/suspended)',
        )

        parser.add_argument(
            '--sleep',
            type=float,
            default=0.2,
            help='Delay between requests in seconds',
        )

    def handle(self, *args, **options):
        exchange = options['exchange']
        letters = options.get('letters')
        sleep = options.get('sleep')

        to_scrape = []
        if exchange in ('TSX', 'both'):
            to_scrape.append('TSX')
        if exchange in ('TSXV', 'both'):
            to_scrape.append('TSXV')

        status = options.get('status')
        if not letters:
            # A-Z and 0-9 as the directory options for all statuses — JSON per-letter works for delisted/suspended
            letters = [chr(c) for c in range(ord('A'), ord('Z') + 1)] + ['0-9']

        self.stdout.write(self.style.NOTICE(f'Starting scrape for exchanges: {to_scrape}'))

        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; TSX-Scraper/1.0)',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': urljoin(BASE_URL, LISTING_PATH),
        }

        for exch in to_scrape:
            exch_key = exch.lower()
            # For delisted/suspended the site exposes a single status page without letters.
            if status in ('delisted', 'suspended'):
                self.stdout.write(f'Fetching status page for {exch} (status={status})...')
                try:
                    params = {'exchange': exch_key}
                    resp = session.get(urljoin(BASE_URL, LISTING_PATH), params=params, headers=headers, timeout=30)
                    resp.raise_for_status()
                except Exception as e:
                    self.stderr.write(f'Failed to fetch status page for {exch} {status}: {e}')
                    continue

                soup = BeautifulSoup(resp.text, 'lxml')
                rows = soup.select('table#tresults tbody tr') or soup.select('table tbody tr') or soup.select('.listed-company-directory__result-row')
                if not rows:
                    self.stdout.write(f'No results for {exch} {status}')
                    continue

                count = 0
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
                                dclean = date_text.replace('\u00A0', ' ').replace('.', '').strip()
                                for fmt in ('%b %d, %Y', '%B %d, %Y'):
                                    try:
                                        status_date = datetime.strptime(dclean, fmt).date()
                                        break
                                    except Exception:
                                        continue
                            except Exception:
                                status_date = None

                    if status == 'listed':
                        Listing.objects.update_or_create(
                            exchange=exch,
                            symbol=symbol,
                            defaults={'name': name, 'listing_url': listing_url, 'status': status, 'active': True, 'status_date': status_date}
                        )
                    elif status == 'delisted':
                        DelistedListing.objects.update_or_create(
                            exchange=exch,
                            symbol=symbol,
                            defaults={'name': name, 'listing_url': listing_url, 'delisted_date': status_date}
                        )
                    else:
                        SuspendedListing.objects.update_or_create(
                            exchange=exch,
                            symbol=symbol,
                            defaults={'name': name, 'listing_url': listing_url}
                        )
                    count += 1

                self.stdout.write(self.style.SUCCESS(f'Found {count} entries for {exch} (status={status})'))
                continue

            # Listed: iterate letters and use JSON API when available
            for letter in letters:
                self.stdout.write(f'Fetching {exch} letter {letter} (status={status})...')

                # Try JSON API first when letter is present
                json_url = None
                if letter:
                    json_url = f"{BASE_URL}/json/company-directory/search/{exch_key}/{letter}"
                data = None
                try:
                    if json_url:
                        jr = session.get(json_url, headers=headers, timeout=30)
                        jr.raise_for_status()
                        data = jr.json()
                except Exception as e:
                    self.stderr.write(f'JSON request failed for {exch} {letter}: {e}')

                count = 0
                if data and isinstance(data, dict) and data.get('results'):
                    for item in data.get('results', []):
                        instruments = item.get('instruments') or []
                        if not instruments:
                            sym = item.get('symbol')
                            name = item.get('name') or ''
                            listing_url = f"https://money.tmx.com/en/quote/{sym}/" if sym else None
                            if sym:
                                Listing.objects.update_or_create(
                                    exchange=exch,
                                    symbol=sym,
                                    defaults={'name': name, 'listing_url': listing_url, 'status': status, 'active': True},
                                )
                                count += 1
                            continue

                        for inst in instruments:
                            sym = inst.get('symbol')
                            inst_name = inst.get('name') or item.get('name')
                            listing_url = f"https://money.tmx.com/en/quote/{sym}/" if sym else None
                            if not sym:
                                continue
                            Listing.objects.update_or_create(
                                exchange=exch,
                                symbol=sym,
                                defaults={'name': inst_name, 'listing_url': listing_url, 'status': status, 'active': True},
                            )
                            count += 1

                    self.stdout.write(self.style.SUCCESS(f'Found {count} entries for {exch} {letter} (json)'))
                    if sleep:
                        time.sleep(sleep)
                    continue
