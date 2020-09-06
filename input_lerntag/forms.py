from django import forms
from .models import Lerntag

class LerntagForm (forms.ModelForm):
    class Meta:
        model = Lerntag
        fields = [
            'datum', 
            'zeit_arbeit_mental',
            'zeit_arbeit_shallow', 
            'zeit_freizeit',
            'zeit_organisation'
        ]