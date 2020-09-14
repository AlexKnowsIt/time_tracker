from django import forms
from .models import Lerntag

class LerntagForm (forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['datum'].widget.attrs.update({'class': 'form-control form-control-sm m-1 bg-dark text-light'})
        self.fields['zeit_arbeit_mental'].widget.attrs.update({'class': 'form-control form-control-sm m-1 bg-dark bg-dark text-light', 'placeholder': 'in Stunden', 'min': 0, 'max': 12})
        self.fields['zeit_arbeit_shallow'].widget.attrs.update({'class': 'form-control form-control-sm m-1 bg-dark text-light', 'placeholder': 'in Stunden', 'min': 0, 'max': 12})
        self.fields['zeit_freizeit'].widget.attrs.update({'class': 'form-control form-control-sm m-1 bg-dark text-light', 'placeholder': 'in Stunden', 'min': 0, 'max': 12})
        self.fields['zeit_organisation'].widget.attrs.update({'class': 'form-control form-control-sm m-1 bg-dark text-light', 'placeholder': 'in Stunden', 'min': 0, 'max': 12})
        self.fields['output_productivity'].widget.attrs.update({'class': 'form-control form-control-sm m-1 border-success bg-dark text-light', 'placeholder': 'von 1 bis 10', 'max': 10})
        self.fields['output_happiness'].widget.attrs.update({'class': 'form-control form-control-sm m-1 bg-dark border-success text-light', 'placeholder': 'von 1 bis 10', 'max': 10})

    class Meta:
        model = Lerntag
        fields = [
            'datum', 
            'zeit_arbeit_mental',
            'zeit_arbeit_shallow', 
            'zeit_freizeit',
            'zeit_organisation',
            'output_productivity',
            'output_happiness'
        ]
