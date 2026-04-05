from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta


DEFAULT_ARGS = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,
}


def load_initial_historical(**context):
    """Initial load of 5 years of daily data for all portfolio symbols."""
    import sys

    sys.path.insert(0, "/app")
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

    import django

    django.setup()

    from stocks.historical_data import (
        get_portfolio_symbols,
        fetch_daily_data,
        upsert_daily_prices,
    )

    symbols = get_portfolio_symbols()
    print(f"Found {len(symbols)} portfolio symbols: {symbols}")

    total_records = 0
    failed = []

    for symbol in symbols:
        print(f"Fetching 5-year daily data for {symbol}...")
        df = fetch_daily_data(symbol, period="5y")
        if df is not None:
            count = upsert_daily_prices(symbol, df)
            total_records += count
            print(f"  -> {count} records")
        else:
            failed.append(symbol)
            print(f"  -> FAILED")

    print(f"\n=== Initial Load Complete ===")
    print(f"Success: {len(symbols) - len(failed)}")
    print(f"Failed: {len(failed)}")
    print(f"Total records: {total_records}")

    return {"status": "success", "total_records": total_records}


def load_incremental_daily(**context):
    """Incremental daily update - fetch only new data since last fetch."""
    import sys

    sys.path.insert(0, "/app")
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

    import django

    django.setup()

    from datetime import date

    from stocks.historical_data import (
        get_portfolio_symbols,
        fetch_daily_data,
        upsert_daily_prices,
        get_last_fetched_date,
    )
    import yfinance as yf

    symbols = get_portfolio_symbols()
    print(f"Checking {len(symbols)} portfolio symbols for updates...")

    total_records = 0
    updated = []

    for symbol in symbols:
        last_date = get_last_fetched_date(symbol)

        if last_date is None:
            print(f"No data for {symbol}, fetching 5 years...")
            df = fetch_daily_data(symbol, period="5y")
        else:
            start_date = last_date + timedelta(days=1)
            end_date = date.today()

            if start_date > end_date:
                print(f"{symbol} is up to date")
                continue

            print(f"Fetching incremental for {symbol} from {start_date}...")

            ticker_symbol = symbol
            if (
                not symbol.endswith(".TO")
                and not symbol.endswith("-")
                and len(symbol) <= 5
            ):
                ticker_symbol = f"{symbol}.TO"

            ticker = yf.Ticker(ticker_symbol)
            df = ticker.history(
                start=start_date.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
                auto_adjust=False,
            )

        if df is not None and not df.empty:
            count = upsert_daily_prices(symbol, df)
            total_records += count
            updated.append(symbol)
            print(f"  -> {count} new records")
        else:
            print(f"  -> No new data")

    print(f"\n=== Incremental Update Complete ===")
    print(f"Updated: {len(updated)}")
    print(f"Total new records: {total_records}")

    return {"status": "success", "total_records": total_records}


with DAG(
    dag_id="historical_daily_loader",
    description="Load daily historical price data for portfolio symbols",
    default_args=DEFAULT_ARGS,
    schedule_interval="0 11 * * *",
    start_date=datetime(2026, 4, 5),
    catchup=False,
    tags=["price_data", "historical"],
) as dag_daily:
    initial_load = PythonOperator(
        task_id="initial_load",
        python_callable=load_initial_historical,
    )

    incremental_load = PythonOperator(
        task_id="incremental_load",
        python_callable=load_incremental_daily,
    )

    incremental_load
