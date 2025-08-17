# Migration to add status_date to Listing
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0004_migrate_recent_to_listed'),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='status_date',
            field=models.DateField(blank=True, null=True, help_text='Date when status (delisted/suspended) occurred'),
        ),
    ]
