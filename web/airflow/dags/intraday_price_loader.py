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


def load_intraday_15m(**context):
    """Load 15-minute intraday data for all portfolio symbols."""
    import sys

    sys.path.insert(0, "/app")
    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

    import django

    django.setup()

    from stocks.historical_data import (
        get_portfolio_symbols,
        fetch_intraday_data,
        upsert_intraday_prices,
    )

    symbols = get_portfolio_symbols()
    print(f"Loading intraday 15m data for {len(symbols)} symbols...")

    interval = "15m"
    total_records = 0
    failed = []

    for symbol in symbols:
        print(f"Fetching {interval} data for {symbol}...")
        df = fetch_intraday_data(symbol, interval=interval)
        if df is not None:
            count = upsert_intraday_prices(symbol, df, interval=interval)
            total_records += count
            print(f"  -> {count} records")
        else:
            failed.append(symbol)
            print(f"  -> FAILED")

    print(f"\n=== Intraday 15m Load Complete ===")
    print(f"Success: {len(symbols) - len(failed)}")
    print(f"Failed: {len(failed)}")
    print(f"Total records: {total_records}")

    return {"status": "success", "total_records": total_records}


with DAG(
    dag_id="intraday_price_loader",
    description="Load intraday 15-min price data for portfolio symbols",
    default_args=DEFAULT_ARGS,
    schedule_interval="*/30 14-21 * * 1-5",
    start_date=datetime(2026, 4, 5),
    catchup=False,
    tags=["price_data", "intraday"],
) as dag_intraday:
    load_intraday = PythonOperator(
        task_id="load_intraday_15m",
        python_callable=load_intraday_15m,
    )

    load_intraday
