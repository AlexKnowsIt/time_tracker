from django.db import models
from datetime import date
from django.utils.timezone import now
from django.contrib.auth.models import User
# Create your models here.

class Lerntag (models.Model):
    datum = models.DateField(default=now)
    zeit_arbeit_mental = models.DecimalField(decimal_places=1, max_digits=3, null=False, blank=False)
    zeit_arbeit_shallow = models.DecimalField(decimal_places=1, max_digits=3, null=False, blank=False)
    zeit_freizeit = models.DecimalField(decimal_places=1, max_digits=3, null=False, blank=False)
    zeit_organisation = models.DecimalField(decimal_places=1, max_digits=3, null=False, blank=False)
    output_productivity = models.PositiveIntegerField(null=True, blank=False)
    output_happiness = models.PositiveIntegerField(null=True, blank=False)
    student = models.ForeignKey(User, on_delete=models.CASCADE, null=True) # wie bekomme ich Standardfeld auf current user?