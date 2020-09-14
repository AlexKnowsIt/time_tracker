from django.db import models
import datetime
# Create your models here.

class Events(models.Model):
    even_id = models.AutoField(primary_key=True)
    event_name = models.CharField(max_length=255,null=True,blank=True)
    jetzt = datetime.datetime.now()
    start_date = models.DateTimeField(null=True,blank=True, default=jetzt)
    end_date = models.DateTimeField(null=True,blank=True, default=jetzt + datetime.timedelta(hours=2))
    deep_work = 'DW'
    shallow_work = 'SW'
    freizeit = 'FZ'
    organisation = 'ORG'
    TIME_CHOICES = [
        (deep_work, 'Deepwork'),
        (shallow_work, 'Shallow Work'),
        (freizeit, 'Freizeit'),
        (organisation, 'Organisation'),
    ]
    event_type = models.CharField(
        max_length=3,
        choices=TIME_CHOICES,
        default=shallow_work,
    )

    def __str__(self):
        return self.event_name