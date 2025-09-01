from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from datetime import datetime, timedelta
import re

DEFAULT_ARGS = {
    'owner': 'airflow',
    'depends_on_past': False,
}

# Letters A-Z and the numeric bucket '0-9' (the TMX directory uses '0-9' as a single option)
LETTERS = [chr(c) for c in range(ord('A'), ord('Z') + 1)] + ['0-9']
EXCHANGES = ['TSX', 'TSXV']
# Add CBOE and CSE as separate sources
EXCHANGES_EXTRA = ['CBOE', 'CSE']
# Status buckets we support. 'listed' has alphabet filters; 'delisted' and 'suspended' do not.
STATUSES = ['listed', 'delisted', 'suspended']


def create_cse_group(dag):
    """Create the CSE task group."""
    with TaskGroup(group_id='CSE_group', dag=dag) as group:
        PythonOperator(
            task_id='cse_listings',
            python_callable=lambda **kwargs: importlib.import_module('cse_handler').process_cse_listings(**kwargs),
            dag=dag
        )
    return group

def _summarize(**context):
    # Collect xcoms from all per-letter tasks and parse numbers like 'Found 131 entries'
    ti = context['ti']
    totals = {}
    overall = 0
    pattern = re.compile(r'Found\s+(\d+)\s+entries', re.IGNORECASE)

    # iterate task ids pushed in XComs across statuses and letters
    for exch in EXCHANGES:
        totals[exch] = 0
        for status in STATUSES:
            for letter in LETTERS:
                sanitized = re.sub(r'[^0-9A-Za-z]', '_', letter)
                task_id = f'{exch.lower()}_{status}_letter_{sanitized}'
                try:
                    val = ti.xcom_pull(task_ids=f'{exch}_group.{task_id}')
                except Exception:
                    val = None
                if not val:
                    continue
                m = pattern.search(val)
                if m:
                    n = int(m.group(1))
                    totals[exch] += n
                    overall += n

    # Log summary
    msg_lines = [f'TSX Scrape summary: total={overall}'] + [f'{k}={v}' for k, v in totals.items()]
    print('\n'.join(msg_lines))
    return {'overall': overall, 'per_exchange': totals}


with DAG(
    dag_id='tsx_listing_scraper',
    default_args=DEFAULT_ARGS,
    description='Run scraper image to fetch TSX/TSXV listings (parallel per-letter)',
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_tasks=10,
    concurrency=12,
) as dag:

    # Create TaskGroups — one per exchange — containing per-letter DockerOperator tasks
    groups = []
    # Robust cross-platform import - __init__.py preferred, path fallback
    def _call_scraper_by_path(exchange, letter, status='listed'):
        try:
            # First try: clean package import (works with __init__.py)
            import scraper_no_django as module
        except ImportError:
            try:
                # Fallback: add current directory to path
                import sys
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                if current_dir not in sys.path:
                    sys.path.insert(0, current_dir)
                import scraper_no_django as module
            except ImportError as e:
                raise RuntimeError(f'scraper_no_django module not found: {e}')
        
        # module may expose run_scrape_letter that accepts (exchange, letter, status)  
        if hasattr(module, 'run_scrape_letter'):
            try:
                return module.run_scrape_letter(exchange, letter, status)
            except TypeError:
                # older signature fallback
                return module.run_scrape_letter(exchange, letter)
        # fallback to status page parser
        if hasattr(module, 'run_scrape_status_page'):
            return module.run_scrape_status_page(exchange, status)
        raise RuntimeError('scraper_no_django does not expose expected functions')

    # Use PythonOperator to run the scraper in-process in Airflow (no docker socket required)
    for exch in EXCHANGES:
        with TaskGroup(group_id=f'{exch}_group') as tg:
            for status in STATUSES:
                if status in ('delisted', 'suspended'):
                    # single status-page task (no letters)
                    task_id = f"{exch.lower()}_{status}"
                    PythonOperator(
                        task_id=task_id,
                        python_callable=lambda e=exch, s=status: _call_scraper_by_path(e, None, s),
                        retries=2,
                        retry_delay=timedelta(minutes=5),
                        provide_context=True,
                    )
                else:
                    # listed: keep per-letter parallel tasks
                    for letter in LETTERS:
                        sanitized = re.sub(r'[^0-9A-Za-z]', '_', letter)
                        task_id = f'{exch.lower()}_{status}_letter_{sanitized}'
                        PythonOperator(
                            task_id=task_id,
                            python_callable=lambda e=exch, l=letter, s=status: _call_scraper_by_path(e, l, s),
                            retries=2,
                            retry_delay=timedelta(minutes=5),
                            provide_context=True,
                        )

        groups.append(tg)

    # Add a separate TaskGroup for CBOE which uses the CSV download. This mirrors the
    # other groups but calls the scraper's CBOE CSV function which returns a simple
    # "Found N entries" string.
    with TaskGroup(group_id='cboe_group') as cboe_tg:
        # Robust cross-platform import
        def _call_cboe():
            try:
                # First try: clean package import (works with __init__.py)
                import scraper_no_django as module
            except ImportError:
                try:
                    # Fallback: add current directory to path
                    import sys
                    import os
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    if current_dir not in sys.path:
                        sys.path.insert(0, current_dir)
                    import scraper_no_django as module
                except ImportError as e:
                    raise RuntimeError(f'scraper_no_django module not found: {e}')
            
            if hasattr(module, 'run_scrape_cboe'):
                return module.run_scrape_cboe('CBOE')
            raise RuntimeError('scraper_no_django does not expose run_scrape_cboe')

        PythonOperator(
            task_id='cboe_fetch_csv',
            python_callable=_call_cboe,
            retries=2,
            retry_delay=timedelta(minutes=5),
            provide_context=True,
        )

    groups.append(cboe_tg)

    # CSE group (XLSX export)
    with TaskGroup(group_id='cse_group') as cse_tg:
        def _call_cse(**context):
            import sys
            from pathlib import Path
            # Add the dags directory to Python path
            dags_dir = Path(__file__).resolve().parent
            if str(dags_dir) not in sys.path:
                sys.path.append(str(dags_dir))
            from cse_handler import process_cse_listings
            return process_cse_listings(**context)

        PythonOperator(
            task_id='cse_fetch_xlsx',
            python_callable=_call_cse,
            retries=3,
            retry_delay=timedelta(minutes=2),
            provide_context=True,
        )

    groups.append(cse_tg)

    summarize = PythonOperator(
        task_id='summarize_results',
        python_callable=_summarize,
        provide_context=True,
    )

    # Run all groups in parallel then summarize
    for g in groups:
        g >> summarize
