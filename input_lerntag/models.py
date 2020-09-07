from django.db import models
from datetime import date
from django.utils.timezone import now
# Create your models here.

class Lerntag (models.Model):
    datum = models.DateField(default=now)
    zeit_arbeit_mental = models.DecimalField(decimal_places=1, max_digits=3, default=0)
    zeit_arbeit_shallow = models.DecimalField(decimal_places=1, max_digits=3, default=0)
    zeit_freizeit = models.DecimalField(decimal_places=1, max_digits=3, default=0)
    zeit_organisation = models.DecimalField(decimal_places=1, max_digits=3, default=0)