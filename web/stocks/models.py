from django.db import models


class Stock(models.Model):
    symbol = models.CharField(max_length=16, db_index=True)
    date = models.DateField(null=True, blank=True)
    open_price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    high_price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    low_price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    close_price = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    volume = models.BigIntegerField(null=True, blank=True)
    source_url = models.URLField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scraped_at']

    def __str__(self):
        return f"{self.symbol} {self.date or ''}"


class Listing(models.Model):
    EXCHANGE_CHOICES = (
        ('TSX', 'TSX'),
        ('TSXV', 'TSX Venture Exchange'),
    )

    exchange = models.CharField(max_length=8, choices=EXCHANGE_CHOICES, db_index=True)
    symbol = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=255)
    # status tracks whether the row is currently listed, recently listed, delisted or suspended
    STATUS_CHOICES = (
        ('listed', 'Currently Listed'),
        ('delisted', 'Recently Delisted'),
        ('suspended', 'Suspended'),
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='listed', db_index=True)
    # active is a convenience boolean: True when listed or recent, False for delisted/suspended
    active = models.BooleanField(default=True, db_index=True)
    # Optional date associated with the status (e.g. delisted date or suspension date)
    status_date = models.DateField(null=True, blank=True, help_text='Date when status (delisted/suspended) occurred')
    listing_url = models.URLField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('exchange', 'symbol')
        ordering = ['exchange', 'symbol']

    def __str__(self):
        return f"{self.exchange}:{self.symbol} — {self.name}"

class DelistedListing(models.Model):
    """Separate table for delisted entries to avoid modifying current stocks_listing flow."""
    exchange = models.CharField(max_length=8, choices=Listing.EXCHANGE_CHOICES, db_index=True)
    symbol = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=255)
    listing_url = models.URLField(null=True, blank=True)
    delisted_date = models.DateField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scraped_at']
        unique_together = ('exchange', 'symbol')

    def __str__(self):
        return f"{self.exchange}:{self.symbol} (delisted) — {self.name}"

class SuspendedListing(models.Model):
    """Separate table for suspended entries."""
    exchange = models.CharField(max_length=8, choices=Listing.EXCHANGE_CHOICES, db_index=True)
    symbol = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=255)
    listing_url = models.URLField(null=True, blank=True)
    suspended_date = models.DateField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scraped_at']
        unique_together = ('exchange', 'symbol')

    def __str__(self):
        return f"{self.exchange}:{self.symbol} (suspended) — {self.name}"
