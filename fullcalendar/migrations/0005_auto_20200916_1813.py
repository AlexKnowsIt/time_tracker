# Generated by Django 3.0.8 on 2020-09-16 16:13

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fullcalendar', '0004_auto_20200915_0046'),
    ]

    operations = [
        migrations.AlterField(
            model_name='events',
            name='end_date',
            field=models.DateTimeField(blank=True, default=datetime.datetime(2020, 9, 16, 20, 13, 16, 130463), null=True),
        ),
        migrations.AlterField(
            model_name='events',
            name='start_date',
            field=models.DateTimeField(blank=True, default=datetime.datetime(2020, 9, 16, 18, 13, 16, 130463), null=True),
        ),
    ]
