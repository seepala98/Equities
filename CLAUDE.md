# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Django-based Canadian equity market analysis platform. Tracks TSX/TSXV/CSE listings, ETF holdings composition, sector/geographic allocation, and investment performance. Uses Apache Airflow for scheduled data scraping, PostgreSQL for persistence, Redis for caching, and a React+Vite frontend served through Nginx.

## Free Data Sources

**Rule: No paid API endpoints. All data must come from free/open-source sources only.**

Currently in use:
- **yfinance** — Yahoo Finance (prices, dividends, fundamentals, ETF info, sector data). Primary source for all ticker data. Python library, no API key needed.
- **BeautifulSoup4 + requests** — HTML scraping for TSX/TSXV/CSE exchange listing pages.
- **Playwright** — Used in Airflow container for the CSE XLSX export (JavaScript-rendered button, file download interception). Replaces the old Selenium + undetected-chromedriver + Xvfb stack.
- **CBOE Canada CSV** — Direct CSV download, no auth required.

Approved free sources to integrate (no API key or cost):

| Source | What it provides | Access method | Notes |
|---|---|---|---|
| **yfinance** | Prices, dividends, fundamentals, ETF holdings, sector/industry | Python library | Already in use |
| **TMX Money** | TSX/TSXV listings directly from the source exchange | HTML scraping | More authoritative than third-party |
| **CBOE Canada** | CBOE-listed equities | CSV download | Already in use |
| **CSE** | CSE listings | XLSX download via Selenium | Already in use |
| **OpenFIGI** | ISIN, FIGI, security identifiers, asset class metadata | Free REST API, no auth needed | `https://api.openfigi.com/v3/mapping` |
| **Bank of Canada** | CAD/USD FX rates, interest rates, policy rate history | Free public REST API | `https://www.bankofcanada.ca/valet/` |
| **Statistics Canada** | GDP, CPI, employment, macro indicators | Free public REST API | `https://www150.statcan.gc.ca/t1/tbl1/` |
| **SEDAR+** | Canadian public company filings (financials, MD&A) | HTML scraping | `https://www.sedarplus.ca` |
| **EDGAR (SEC)** | US company filings for cross-listed stocks | Free REST API | `https://data.sec.gov/api/xbrl/` |
| **Wikipedia / Wikidata** | Company descriptions, HQ country, founding date | MediaWiki API / SPARQL | No auth needed |
| **World Bank Open Data** | Country-level macro data (GDP per capita, inflation) | Free REST API | `https://api.worldbank.org/v2/` |
| **UN Comtrade** | Trade data by country/commodity | Free public API | Useful for commodity ETF context |

Do NOT add or suggest any paid sources: Bloomberg, Refinitiv/LSEG, FactSet, Morningstar Direct, IEX Cloud paid tier, Alpha Vantage paid tier, Intrinio, Quandl/Nasdaq Data Link paid datasets, or any service requiring a subscription or per-call payment.

## First-Time Setup

```bash
# Copy env file and configure secrets
cp .env.example .env
# Edit .env — at minimum change POSTGRES_PASSWORD and DJANGO_SECRET_KEY

# Start everything
docker compose up --build
```

Services after startup:

| Service | URL |
|---|---|
| App (via Nginx) | http://localhost |
| Django API | http://localhost/api/v1/ |
| Django Admin | http://localhost/admin/ |
| Airflow UI | http://localhost:8081 (admin / see .env) |
| pgAdmin | http://localhost:8080 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 (admin / see .env) |

## Common Commands

```bash
# Run Django management commands
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py scrape_tsx_listings --exchange=both
docker compose exec web python manage.py populate_sector_cache

# Run backend tests (pytest)
docker compose exec web pytest stocks/tests.py -v

# Run a single test class
docker compose exec web pytest stocks/tests.py::APIETFTest -v

# Frontend dev server (hot reload, proxies API to web:8000)
cd frontend && npm install && npm run dev
# Then visit http://localhost:3000

# Frontend production build
cd frontend && npm run build
```

## Architecture

### Service topology

```
Browser
  └─► Nginx (:80)
        ├─► React frontend (static, served by nginx SPA container)
        ├─► /api/v1/  ──► Django (DRF API, :8000)
        ├─► /admin/   ──► Django
        └─► /metrics  ──► Django (Prometheus scrape target)

Django ──► PostgreSQL (:5432)
       ──► Redis (:6379)  ← cache + sessions

Airflow (webserver :8081, scheduler)
  ──► PostgreSQL (shared DB)
  ──► DAGs scrape yfinance + exchange websites → PostgreSQL

Prometheus (:9090) ──scrapes──► Django /metrics
Grafana (:3001)    ──reads──►  Prometheus
```

### Backend (`web/`)

**`web/stocks/models.py`** — All models:
- `Listing` — Active exchange listings with 13-type asset classification
- `DelistedListing` / `SuspendedListing` — Separate tables (keeps `Listing` clean)
- `Stock` — Time-series OHLCV price data
- `ETFInfo` — ETF metadata (MER, AUM, benchmark)
- `ETFHolding` — ETF-to-stock relationships with weight percentages and as-of dates
- `ETFSectorAllocation` / `ETFGeographicAllocation` — Aggregated allocation tables
- `YFinanceSectorCache` / `YFinanceStockSectorCache` — 24hr/7-day caches
- `EnrichedTickerData` — Versioned comprehensive ticker data with hash-based change detection

**`web/stocks/serializers.py`** — DRF serializers for all models including read-only computed fields (`aum_formatted`, `mer_formatted`, `weight_formatted`).

**`web/stocks/api_views.py`** — DRF API views. All list endpoints are paginated (50/page), support `search` and `ordering` query params. Key endpoints:
- `GET /api/v1/listings/?exchange=TSX&asset_type=ETF&search=shop`
- `GET /api/v1/etfs/<symbol>/` — ETF detail with inline holdings, sector, geographic allocations
- `GET/POST /api/v1/etfs/performance/?symbol=XGRO&investment_amount=10000&start_date=2020-01-01`
- `GET /api/v1/enriched/<symbol>/` — Latest enriched ticker data

**`web/stocks/api_urls.py`** — API URL routing under `/api/v1/`.

**`web/stocks/views.py`** — Legacy Django template views (still served for non-API access). All N+1 queries fixed; uses `select_related`, `annotate`, `.only()`.

**`web/project/settings.py`** — Django settings with Redis cache (django-redis), DRF, CORS, django-prometheus, and PostgreSQL via `django_prometheus.db.backends.postgresql`.

### Frontend (`frontend/`)

React 18 + Vite + Tailwind CSS. Pages: Dashboard, ETF Analysis, ETF Holdings, Listings, Sector Analysis.

- `src/api.js` — Axios client wrapping all `/api/v1/` endpoints
- `src/pages/` — One file per page
- `src/components/` — `Spinner`, `ErrorAlert`, `StatCard`
- Charts: Chart.js via react-chartjs-2 (Bar, Line, Doughnut)
- Data tables: TanStack Table (server-side pagination)

In development, Vite proxies `/api` to `http://web:8000` (configured in `vite.config.js`).

### Caching strategy

| Cache | Backend | TTL | Invalidation |
|---|---|---|---|
| Django view/API cache | Redis | 5 min default | Automatic expiry |
| ETF performance results | Redis | 1 hour | Automatic expiry |
| Asset type summary | Redis | 10 min | Automatic expiry |
| `YFinanceSectorCache` | PostgreSQL | 24 hours | `is_cache_fresh` property |
| `YFinanceStockSectorCache` | PostgreSQL | 7 days | `is_cache_fresh` property |
| `EnrichedTickerData` | PostgreSQL | Versioned | SHA-256 hash change detection |

Redis gracefully degrades (`IGNORE_EXCEPTIONS: True`) — if Redis is down the app still works without caching.

### Kubernetes (`k8s/`)

Apply in order: `namespace.yaml` → `secrets.yaml` → `configmap.yaml` → `postgres.yaml` → `redis.yaml` → `django.yaml` → `frontend.yaml` → `nginx.yaml` → `airflow.yaml` → `prometheus.yaml` → `grafana.yaml`. See `k8s/README.md`.

### Observability

- Django metrics exposed at `/metrics` via `django-prometheus`
- Prometheus scrapes `/metrics` every 15s
- Grafana dashboard pre-provisioned at `grafana/dashboards/django.json` (request rate, latency p95, cache hit rate, DB queries/s)

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_DB` | `stockdb` | Database name |
| `POSTGRES_USER` | `stockuser` | DB user |
| `POSTGRES_PASSWORD` | `changeme` | DB password — **change this** |
| `DJANGO_SECRET_KEY` | `dev-secret` | Django secret — **change this in prod** |
| `DJANGO_DEBUG` | `1` | Set to `0` in production |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `CORS_ALLOWED_ORIGINS` | `` | Comma-separated allowed origins (prod) |

## Testing

Tests use pytest-django with factory-boy. Factories are in `web/stocks/factories.py`. Test file: `web/stocks/tests.py`.

```bash
# Run all tests
docker compose exec web pytest -v

# Run a specific test
docker compose exec web pytest stocks/tests.py::AssetClassifierTest::test_classifies_etf_by_name -v
```

CI runs automatically on push/PR via `.github/workflows/ci.yml` (Django tests + React build + Docker smoke test).
