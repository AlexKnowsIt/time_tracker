# Generated by Django 3.0.8 on 2020-09-14 22:22

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('input_lerntag', '0006_lerntag_student'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lerntag',
            name='datum',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
