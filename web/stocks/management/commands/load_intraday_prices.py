from django.core.management.base import BaseCommand
from stocks.historical_data import update_intraday_for_all_symbols


class Command(BaseCommand):
    help = "Load intraday 15-min price data for all portfolio symbols"

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=str,
            default="15m",
            help="Intraday interval (default: 15m)",
        )
        parser.add_argument(
            "--symbols",
            nargs="+",
            type=str,
            help="Specific symbols to load (default: all portfolio symbols)",
        )

    def handle(self, *args, **options):
        interval = options["interval"]

        self.stdout.write(
            f"Loading intraday data ({interval}) for portfolio symbols..."
        )

        results = update_intraday_for_all_symbols(interval=interval)

        self.stdout.write(
            self.style.SUCCESS(
                f"Completed! Success: {len(results['success'])}, "
                f"Failed: {len(results['failed'])}, "
                f"Total records: {results['total_records']}"
            )
        )

        if results["failed"]:
            self.stdout.write(
                self.style.WARNING(f"Failed symbols: {', '.join(results['failed'])}")
            )
