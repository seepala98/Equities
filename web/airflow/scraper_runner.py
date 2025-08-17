"""Helper for Airflow PythonOperator to call Django management command logic in-process.

This script sets DJANGO_SETTINGS_MODULE and initializes Django, then imports and invokes the
existing scraping logic in a programmatic way.
"""
import os
import django
from django.core import management

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
# Django will be configured by the Airflow image which will have project files copied
django.setup()


def run_scrape_letter(exchange: str, letter: str) -> str:
    """Run the management command for a single letter and return its stdout as a string.
    We call the management command programmatically and capture printed output by temporarily
    redirecting stdout.
    """
    import io
    import sys

    buf = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = buf
        management.call_command('scrape_tsx_listings', exchange=exchange, letters=[letter], stdout=buf)
    finally:
        sys.stdout = old_stdout

    return buf.getvalue()
