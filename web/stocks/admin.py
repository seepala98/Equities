from django.contrib import admin
from .models import Stock, Listing


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'date', 'close_price', 'volume', 'scraped_at')
    search_fields = ('symbol',)
    list_filter = ('symbol',)


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('exchange', 'symbol', 'name', 'scraped_at')
    search_fields = ('symbol', 'name')
    list_filter = ('exchange',)
