from django.db import models
from datetime import date
# Create your models here.

class Lerntag (models.Model):
    Date = date.today()
    datum = models.DateField(default=Date)
    notiz = models.TextField(blank=True, null=True)
    zeit_lernen = models.DecimalField(decimal_places=2, max_digits=4)
    zeit_freizeit = models.DecimalField(decimal_places=2, max_digits=4)
    zeit_freundin = models.DecimalField(decimal_places=2, max_digits=4)