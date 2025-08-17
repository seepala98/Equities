# Data migration: convert 'recent' status to 'listed'
from django.db import migrations


def forwards(apps, schema_editor):
    Listing = apps.get_model('stocks', 'Listing')
    Listing.objects.filter(status='recent').update(status='listed', active=True)


def backwards(apps, schema_editor):
    Listing = apps.get_model('stocks', 'Listing')
    Listing.objects.filter(status='listed').update(status='recent')


class Migration(migrations.Migration):
    dependencies = [
        ('stocks', '0003_listing_status_active'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
