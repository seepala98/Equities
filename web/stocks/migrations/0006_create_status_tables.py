# Migration to add DelistedListing and SuspendedListing tables
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0005_add_status_date'),
    ]

    operations = [
        migrations.CreateModel(
            name='DelistedListing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('exchange', models.CharField(choices=[('TSX', 'TSX'), ('TSXV', 'TSX Venture Exchange')], max_length=8, db_index=True)),
                ('symbol', models.CharField(max_length=32, db_index=True)),
                ('name', models.CharField(max_length=255)),
                ('listing_url', models.URLField(blank=True, null=True)),
                ('delisted_date', models.DateField(blank=True, null=True)),
                ('scraped_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-scraped_at'], 'unique_together': {('exchange', 'symbol')}},
        ),
        migrations.CreateModel(
            name='SuspendedListing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('exchange', models.CharField(choices=[('TSX', 'TSX'), ('TSXV', 'TSX Venture Exchange')], max_length=8, db_index=True)),
                ('symbol', models.CharField(max_length=32, db_index=True)),
                ('name', models.CharField(max_length=255)),
                ('listing_url', models.URLField(blank=True, null=True)),
                ('suspended_date', models.DateField(blank=True, null=True)),
                ('scraped_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-scraped_at'], 'unique_together': {('exchange', 'symbol')}},
        ),
    ]
