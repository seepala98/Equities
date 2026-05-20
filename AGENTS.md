# AGENTS.md

## Critical Rules

- **No paid data sources.** All data must come from free/open-source sources only. See `CLAUDE.md` for the approved source table. Never suggest Bloomberg, Refinitiv, FactSet, Morningstar Direct, or any paid API.
- **All backend commands run inside Docker.** Use `docker compose exec web ...` for Django management commands, tests, and shell access. Do not run `python manage.py` directly on the host.
- **Never commit `.env`.** Copy from `.env.example` and change at minimum `POSTGRES_PASSWORD` and `DJANGO_SECRET_KEY`.

## Developer Commands

```bash
# Start everything
docker compose up --build

# Django management commands (inside container)
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py scrape_tsx_listings --exchange=both
docker compose exec web python manage.py populate_sector_cache
docker compose exec web python manage.py scrape_vettafi_indexes              # scrape all categories
docker compose exec web python manage.py scrape_vettafi_indexes --category=equity_benchmark  # single category
docker compose exec web python manage.py scrape_vettafi_indexes --dry-run     # preview without saving

# Tests — run from repo root
docker compose exec web pytest -v                          # all tests
docker compose exec web pytest stocks/tests.py::APIETFTest -v  # single class
docker compose exec web pytest stocks/tests.py::AssetClassifierTest::test_classifies_etf_by_name -v  # single test

# Lint (flake8 — CI runs this)
docker compose exec web flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
docker compose exec web flake8 . --count --max-line-length=120 --exclude=migrations --statistics

# Frontend dev (hot reload, proxies /api to web:8000)
cd frontend && npm run dev    # then visit http://localhost:3000

# Frontend lint
cd frontend && npm run lint   # eslint src --ext .js,.jsx

# Frontend production build
cd frontend && npm run build
```

## CI Pipeline (`.github/workflows/ci.yml`)

Order: **flake8 lint → migrate → pytest → frontend build → Docker smoke test**
- Python 3.11, Node 20
- Test DB: `stockdb_test` with user `stockuser` / `testpass`
- Flake8: `E9,F63,F7,F82` are hard errors; line length 120; migrations excluded
- Smoke test hits `/api/v1/listings/` and `/api/v1/etfs/popular/`

## Architecture Quick Reference

```
Browser → Nginx (:80) → React static OR /api/v1/ → Django (:8000)
Django → PostgreSQL (:5432) + Redis (:6379, cache/sessions)
Airflow (:8081) → PostgreSQL (shared DB) → scrapes yfinance + exchanges
Prometheus (:9090) scrapes Django /metrics
Grafana (:3001) reads Prometheus
```

### Key Backend Files

| File | Purpose |
|---|---|
| `web/stocks/models.py` | All models: Listing, Stock, ETFInfo, ETFHolding, ETFSectorAllocation, ETFGeographicAllocation, EnrichedTickerData, VettaFiIndex |
| `web/stocks/api_views.py` | DRF views. All list endpoints paginated (50/page) with `search` + `ordering` params |
| `web/stocks/serializers.py` | DRF serializers with computed read-only fields (`_formatted` suffix) |
| `web/stocks/asset_classifier.py` | 13-type asset classification logic |
| `web/stocks/enriched_data_service.py` | SHA-256 hash-based change detection for enriched ticker data |
| `web/stocks/vettafi_scraper.py` | VettaFi Index Finder scraper (1,900+ global indexes) |
| `web/stocks/factories.py` | factory-boy factories for tests |
| `web/stocks/tests.py` | All tests live here (single file) |
| `web/project/settings.py` | Django settings — uses `django_prometheus.db.backends.postgresql` |

### Frontend (`frontend/`)

- React 18 + Vite + Tailwind CSS
- `src/api.js` — Axios client wrapping all `/api/v1/` endpoints
- `src/pages/` — One file per page (Dashboard, ETF Analysis, ETF Holdings, Listings, Sector Analysis, Portfolio, PortfolioHeatmap, ImportPortfolio)
- Charts: Chart.js via react-chartjs-2; Tables: TanStack Table (server-side pagination)
- Dev proxy: Vite proxies `/api` to `http://web:8000` (see `vite.config.js`)

## Testing Quirks

- Tests use `pytest-django` with `factory-boy`
- All tests are in a single file: `web/stocks/tests.py`
- Factories in `web/stocks/factories.py`
- Requires PostgreSQL + Redis to be running (CI uses service containers)
- pytest config in `web/pytest.ini`: `DJANGO_SETTINGS_MODULE = project.settings`

## Caching

| Layer | Backend | TTL | Notes |
|---|---|---|---|
| Django view/API cache | Redis | 5 min | `IGNORE_EXCEPTIONS: True` — works without Redis |
| ETF performance | Redis | 1 hour | |
| ETF detail | Redis | 1 hour | Cached in `ETFDetailView.get_object()` |
| Asset type summary | Redis | 10 min | Invalidated after `scrape_tsx_listings` completes |
| YFinanceSectorCache | PostgreSQL | 24 hours | `is_cache_fresh` property |
| YFinanceStockSectorCache | PostgreSQL | 7 days | `is_cache_fresh` property |
| EnrichedTickerData | PostgreSQL | Versioned | SHA-256 hash change detection |

## Performance Optimizations (Implemented)

- **EnrichedTickerListView**: Uses `Subquery` instead of massive `Q()` OR-chain (was 5,000+ clauses)
- **PortfolioSerializer**: `holdings_count` and `total_invested` are DB-annotated, not per-object queries
- **ETFDetailView**: Cache key is now actually used — caches queryset for 1 hour
- **EnrichedDataService**: All methods use `DISTINCT ON` single queries instead of N+1 loops
- **generate_daily_values**: Single transaction fetch + Python running totals (was 365 queries/year)
- **ETF holdings storage**: Uses `bulk_create` instead of per-holding `create()`
- **classify_all_listings**: Uses `bulk_update` in batches of 500 instead of per-listing `save()`
- **BrowsableAPIRenderer**: Only enabled when `DEBUG=True`
- **DB connection pooling**: `CONN_MAX_AGE=600` (10 min persistent connections)
- **Transaction index**: Added index on `(portfolio, transaction_type)` for portfolio aggregations
- **IntradayPrice cleanup**: Airflow DAG purges data older than 7 days
- **Airflow enrichment DAG**: Changed from every 30 min to weekly (Sunday 2 AM)

## Kubernetes

Apply manifests in strict order: `namespace → secrets → configmap → postgres → redis → django → frontend → nginx → airflow → prometheus → grafana`. See `k8s/README.md`.

## Data Sources

- **yfinance** — Primary source for all ticker data (prices, dividends, fundamentals, ETF info). Python library, no API key.
- **BeautifulSoup4 + requests** — HTML scraping for TSX/TSXV/CSE exchange listings and VettaFi Index Finder.
- **Playwright** — CSE XLSX export (JS-rendered button, file download interception). In Airflow container.
- **CBOE Canada CSV** — Direct CSV download.
- **VettaFi Index Finder** — 1,900+ global indexes across equity benchmarks, fixed income, factor, thematic, etc. Scraped from category pages with factsheet/methodology PDFs.

## Existing Instruction Files

- `CLAUDE.md` — Comprehensive architecture docs, approved data sources table, environment variables reference. Read this for detailed model/endpoint/caching info.
