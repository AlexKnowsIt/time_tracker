from django import forms
from .models import Events

class KalenderForm (forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['event_name'].widget.attrs.update({'class': 'form-control form-control-sm m-1 bg-dark text-light', 'placeholder': 'Beschreibung eingeben'})
        self.fields['event_type'].widget.attrs.update({'class': 'form-control form-control-sm m-1 bg-dark text-light', 'placeholder': 'chose option'})

    class Meta:
        model = Events
        fields = [
            'event_name',
            'event_type'
        ]
