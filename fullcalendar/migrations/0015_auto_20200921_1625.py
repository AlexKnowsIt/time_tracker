# Generated by Django 3.0.8 on 2020-09-21 14:25

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fullcalendar', '0014_auto_20200921_1624'),
    ]

    operations = [
        migrations.AlterField(
            model_name='events',
            name='end_date',
            field=models.DateTimeField(blank=True, default=datetime.datetime(2020, 9, 21, 18, 25, 45, 630799), null=True),
        ),
        migrations.AlterField(
            model_name='events',
            name='start_date',
            field=models.DateTimeField(blank=True, default=datetime.datetime(2020, 9, 21, 16, 25, 45, 630799), null=True),
        ),
    ]
