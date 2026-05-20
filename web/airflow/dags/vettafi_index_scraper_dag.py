"""
VettaFi Index Finder DAG
========================

Scrapes all 1,900+ indexes from VettaFi Index Finder and stores them in the database.
Runs weekly to keep index metadata fresh.

Categories scraped:
- Equity Benchmark
- Fixed Income Benchmark
- Factor
- Thematic
- Custom Equity
- Assets
- Derivatives
- Strategy
"""

from datetime import datetime, timedelta
import logging
import sys

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'data-platform-team',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=15),
    'max_active_runs': 1,
}

dag = DAG(
    'vettafi_index_scraper',
    default_args=default_args,
    description='Scrape VettaFi Index Finder for global index coverage (1,900+ indexes)',
    schedule_interval='0 3 * * 0',
    catchup=False,
    max_active_runs=1,
    tags=['vettafi', 'indexes', 'scraper', 'weekly'],
)


def scrape_vettafi_indexes(**context) -> dict:
    """Scrape all VettaFi indexes and store in database."""
    logger.info("Starting VettaFi Index Finder scrape...")

    try:
        sys.path.insert(0, '/opt/airflow/dags')
        from stocks.vettafi_scraper import scrape_all_categories
    except ImportError:
        sys.path.insert(0, '/opt/airflow')
        from stocks.vettafi_scraper import scrape_all_categories

    indexes = scrape_all_categories(max_pages_per_category=50)
    logger.info(f"Scraped {len(indexes)} indexes from VettaFi")

    context['task_instance'].xcom_push(key='scraped_count', value=len(indexes))

    return {
        'scraped_count': len(indexes),
        'categories': list(set(idx.get('category') for idx in indexes)),
    }


def store_vettafi_indexes(**context) -> dict:
    """Store scraped indexes in Django database."""
    logger.info("Storing VettaFi indexes in database...")

    try:
        import django
        import os
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
        django.setup()
    except Exception:
        pass

    from stocks.models import VettaFiIndex
    from stocks.vettafi_scraper import scrape_all_categories

    indexes = scrape_all_categories(max_pages_per_category=50)

    created_count = 0
    updated_count = 0

    for idx_data in indexes:
        ticker = idx_data.pop('ticker')
        obj, created = VettaFiIndex.objects.update_or_create(
            ticker=ticker,
            defaults=idx_data,
        )
        if created:
            created_count += 1
        else:
            updated_count += 1

    result = {
        'created': created_count,
        'updated': updated_count,
        'total': len(indexes),
    }

    logger.info(f"VettaFi indexes stored: {created_count} created, {updated_count} updated")
    context['task_instance'].xcom_push(key='store_result', value=result)

    return result


def generate_vettafi_report(**context) -> str:
    """Generate scrape report."""
    scraped_count = context['task_instance'].xcom_pull(key='scraped_count') or 0
    store_result = context['task_instance'].xcom_pull(key='store_result') or {}

    report = f"""
VettaFi Index Scraper Report
============================
Indexes scraped: {scraped_count}
Created: {store_result.get('created', 0)}
Updated: {store_result.get('updated', 0)}
Total: {store_result.get('total', 0)}
"""

    logger.info(report)
    return report


with dag:
    scrape_task = PythonOperator(
        task_id='scrape_vettafi_indexes',
        python_callable=scrape_vettafi_indexes,
    )

    store_task = PythonOperator(
        task_id='store_vettafi_indexes',
        python_callable=store_vettafi_indexes,
    )

    report_task = PythonOperator(
        task_id='generate_vettafi_report',
        python_callable=generate_vettafi_report,
    )

    scrape_task >> store_task >> report_task
