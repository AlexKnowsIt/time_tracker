# Generated by Django 3.0.8 on 2020-09-10 23:06

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('input_lerntag', '0005_auto_20200911_0028'),
    ]

    operations = [
        migrations.AddField(
            model_name='lerntag',
            name='student',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]