from django.db import models
from datetime import date
from django.utils.timezone import now
from django.contrib.auth.models import User
# Create your models here.

class Lerntag (models.Model):
    datum = models.DateField(default=now)
    zeit_arbeit_mental = models.DecimalField(decimal_places=1, max_digits=3, blank=False)
    zeit_arbeit_shallow = models.DecimalField(decimal_places=1, max_digits=3, blank=False)
    zeit_freizeit = models.DecimalField(decimal_places=1, max_digits=3, blank=False)
    zeit_organisation = models.DecimalField(decimal_places=1, max_digits=3, blank=False)
    output_productivity = models.PositiveIntegerField (blank=False)
    output_happiness = models.PositiveIntegerField (blank=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="lerntag", null=True)