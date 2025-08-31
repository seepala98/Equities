"""
Management command to pre-populate the sector cache with all available sectors.
This can be run periodically (daily) to ensure fresh data is always available.
"""
from django.core.management.base import BaseCommand
from stocks.sector_analysis_utils import SectorAnalyzer
from stocks.models import YFinanceSectorCache
import time


class Command(BaseCommand):
    help = 'Pre-populate the sector cache with data for all available sectors'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-refresh',
            action='store_true',
            help='Force refresh all sectors even if cache is fresh',
        )
        parser.add_argument(
            '--sectors',
            type=str,
            nargs='*',
            help='Specific sector keys to populate (default: all)',
        )

    def handle(self, *args, **options):
        force_refresh = options['force_refresh']
        specific_sectors = options['sectors']
        
        analyzer = SectorAnalyzer()
        
        # Determine which sectors to process
        if specific_sectors:
            sectors_to_process = {}
            for sector_key in specific_sectors:
                if sector_key in analyzer.SECTOR_KEYS:
                    sectors_to_process[sector_key] = analyzer.SECTOR_KEYS[sector_key]
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Unknown sector key: {sector_key}')
                    )
        else:
            sectors_to_process = analyzer.SECTOR_KEYS

        if not sectors_to_process:
            self.stdout.write(
                self.style.ERROR('No valid sectors to process')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f'📊 Starting sector cache population for {len(sectors_to_process)} sectors...')
        )
        
        if force_refresh:
            self.stdout.write('🔄 Force refresh mode: All sectors will be refreshed from API')
        else:
            self.stdout.write('⚡ Smart mode: Only stale/missing sectors will be refreshed')
        
        success_count = 0
        error_count = 0
        cached_count = 0
        total_time = 0
        
        for sector_key, sector_name in sectors_to_process.items():
            start_time = time.time()
            
            # Check if we should skip this sector (not forced and cache is fresh)
            if not force_refresh:
                cached_entry = YFinanceSectorCache.objects.filter(
                    sector_key=sector_key,
                    fetch_success=True
                ).first()
                
                if cached_entry and cached_entry.is_cache_fresh:
                    self.stdout.write(f'💾 {sector_name:20} - Skipped (cache fresh)')
                    cached_count += 1
                    continue
            
            try:
                # This will fetch from API and cache the results
                if force_refresh:
                    # Delete existing cache to force API call
                    YFinanceSectorCache.objects.filter(sector_key=sector_key).delete()
                
                sector_data = analyzer.get_sector_data(sector_key)
                call_time = time.time() - start_time
                total_time += call_time
                
                if sector_data['success']:
                    self.stdout.write(
                        f'✅ {sector_name:20} - Cached successfully ({call_time:.2f}s)'
                    )
                    success_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️  {sector_name:20} - Failed: {sector_data.get("error", "Unknown error")}'
                        )
                    )
                    error_count += 1
                    
            except Exception as e:
                call_time = time.time() - start_time
                total_time += call_time
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ {sector_name:20} - Error: {str(e)}'
                    )
                )
                error_count += 1

        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS(f'🎉 Sector Cache Population Complete!')
        )
        self.stdout.write(f'✅ Successful:     {success_count}')
        self.stdout.write(f'⚠️  Errors:        {error_count}') 
        self.stdout.write(f'💾 Already cached: {cached_count}')
        self.stdout.write(f'⏱️  Total time:    {total_time:.2f} seconds')
        
        if success_count > 0:
            avg_time = total_time / (success_count + error_count) if (success_count + error_count) > 0 else 0
            self.stdout.write(f'📊 Average time:   {avg_time:.2f} seconds per sector')
        
        # Final cache stats
        total_cache_entries = YFinanceSectorCache.objects.count()
        fresh_cache_entries = sum(1 for cache in YFinanceSectorCache.objects.all() if cache.is_cache_fresh)
        
        self.stdout.write(f'\n💾 Cache Statistics:')
        self.stdout.write(f'   Total entries: {total_cache_entries}')
        self.stdout.write(f'   Fresh entries: {fresh_cache_entries}')
        self.stdout.write(f'   Stale entries: {total_cache_entries - fresh_cache_entries}')
        
        if error_count == 0:
            self.stdout.write(
                self.style.SUCCESS('\n🚀 All sector data is now cached and ready for fast access!')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'\n⚠️  {error_count} sectors had issues. Check logs for details.')
            )
