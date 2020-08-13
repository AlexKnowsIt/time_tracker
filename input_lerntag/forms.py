from django import forms
from .models import Lerntag

class LerntagForm (forms.ModelForm):
    class Meta:
        model = Lerntag
        fields = [
            'datum', 
            'notiz', 
            'zeit_lernen', 
            'zeit_freizeit',
            'zeit_freundin'
        ]