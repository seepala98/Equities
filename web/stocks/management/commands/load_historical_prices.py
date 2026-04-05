from django.core.management.base import BaseCommand
from stocks.historical_data import load_historical_for_all_symbols


class Command(BaseCommand):
    help = "Load historical daily price data for all portfolio symbols"

    def add_arguments(self, parser):
        parser.add_argument(
            "--years",
            type=int,
            default=5,
            help="Number of years of historical data to load (default: 5)",
        )
        parser.add_argument(
            "--symbols",
            nargs="+",
            type=str,
            help="Specific symbols to load (default: all portfolio symbols)",
        )

    def handle(self, *args, **options):
        years = options["years"]
        symbols = options.get("symbols")

        self.stdout.write(f"Loading {years} years of historical data...")

        results = load_historical_for_all_symbols(years=years)

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
