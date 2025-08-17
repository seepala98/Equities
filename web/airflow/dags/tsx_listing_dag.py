from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from datetime import datetime, timedelta
import re
import importlib.util
from pathlib import Path

DEFAULT_ARGS = {
    'owner': 'airflow',
    'depends_on_past': False,
}

# Letters A-Z and the numeric bucket '0-9' (the TMX directory uses '0-9' as a single option)
LETTERS = [chr(c) for c in range(ord('A'), ord('Z') + 1)] + ['0-9']
EXCHANGES = ['TSX', 'TSXV']
# Status buckets we support. 'listed' has alphabet filters; 'delisted' and 'suspended' do not.
STATUSES = ['listed', 'delisted', 'suspended']


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
    # Helper to load the scraper_no_django module from the DAGs folder by path.
    def _call_scraper_by_path(exchange, letter, status='listed'):
        # DAG file is located at .../airflow/dags/tsx_listing_dag.py under DAGS_FOLDER
        dag_pkg_dir = Path(__file__).resolve().parents[1]  # points to .../airflow
        candidate = dag_pkg_dir / 'scraper_no_django.py'
        if not candidate.exists():
            # fallback: try directly under DAGS_FOLDER
            candidate = Path(__file__).resolve().parents[2] / 'scraper_no_django.py'
        spec = importlib.util.spec_from_file_location('scraper_no_django', str(candidate))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
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

    summarize = PythonOperator(
        task_id='summarize_results',
        python_callable=_summarize,
        provide_context=True,
    )

    # Run all groups in parallel then summarize
    for g in groups:
        g >> summarize
