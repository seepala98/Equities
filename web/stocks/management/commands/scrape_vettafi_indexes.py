from django.core.management.base import BaseCommand
from stocks.models import VettaFiIndex
from stocks.vettafi_scraper import scrape_all_categories, scrape_category_page
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Scrape VettaFi Index Finder for global index coverage (1,900+ indexes)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--category",
            type=str,
            help="Specific category to scrape (equity_benchmark, fixed_income_benchmark, factor, thematic, custom_equity, assets, derivatives, strategy). If omitted, scrapes all categories.",
        )
        parser.add_argument(
            "--max-pages",
            type=int,
            default=50,
            help="Maximum pagination pages per category (default: 50)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only fetch and display data without saving to database",
        )

    def handle(self, *args, **options):
        category = options.get("category")
        max_pages = options.get("max_pages")
        dry_run = options.get("dry_run")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No data will be saved"))

        if category:
            self.stdout.write(f"Scraping category: {category}")
            indexes = scrape_category_page(category, max_pages)
        else:
            self.stdout.write("Scraping all VettaFi categories...")
            indexes = scrape_all_categories(max_pages)

        if not indexes:
            self.stdout.write(self.style.ERROR("No indexes found!"))
            return

        self.stdout.write(f"Found {len(indexes)} indexes")

        if dry_run:
            for idx in indexes[:10]:
                self.stdout.write(f"  {idx['ticker']}: {idx['name']} ({idx['category']})")
            if len(indexes) > 10:
                self.stdout.write(f"  ... and {len(indexes) - 10} more")
            return

        created_count = 0
        updated_count = 0

        for idx_data in indexes:
            ticker = idx_data.pop("ticker")
            obj, created = VettaFiIndex.objects.update_or_create(
                ticker=ticker,
                defaults=idx_data,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"VettaFi scrape complete: {created_count} created, {updated_count} updated, "
            f"total {len(indexes)} indexes"
        ))
