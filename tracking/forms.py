from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import Eintrag, Kategorie, Tagesbewertung

DT_FORMAT = "%Y-%m-%dT%H:%M"
DT_FORMATE = [DT_FORMAT, "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"]


def _dt_feld(label, required=True):
    return forms.DateTimeField(
        label=label,
        required=required,
        input_formats=DT_FORMATE,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DT_FORMAT),
    )


class EintragForm(forms.ModelForm):
    start = _dt_feld("Start")
    ende = _dt_feld("Ende")

    class Meta:
        model = Eintrag
        fields = ["kategorie", "start", "ende", "notiz"]
        widgets = {"notiz": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, nutzer, **kwargs):
        super().__init__(*args, **kwargs)
        self.nutzer = nutzer
        auswahl = Q(aktiv=True)
        if self.instance.pk:
            auswahl |= Q(pk=self.instance.kategorie_id)
        self.fields["kategorie"].queryset = Kategorie.objects.filter(auswahl, nutzer=nutzer)
        # Nur ein laufender Eintrag darf das Ende leer lassen.
        laeuft = bool(self.instance.pk) and self.instance.ende is None
        self.fields["ende"].required = not laeuft

    def clean(self):
        daten = super().clean()
        start, ende = daten.get("start"), daten.get("ende")
        if start and ende and ende <= start:
            self.add_error("ende", "Das Ende muss nach dem Start liegen.")
        elif start:
            andere = Eintrag.objects.filter(nutzer=self.nutzer).exclude(pk=self.instance.pk)
            andere = andere.filter(Q(ende__isnull=True) | Q(ende__gt=start))
            if ende:
                andere = andere.filter(start__lt=ende)
            kollision = andere.select_related("kategorie").order_by("start").first()
            if kollision:
                von = timezone.localtime(kollision.start).strftime("%d.%m. %H:%M")
                bis = (
                    timezone.localtime(kollision.ende).strftime("%H:%M")
                    if kollision.ende
                    else "läuft"
                )
                raise forms.ValidationError(
                    f"Überschneidung mit „{kollision.kategorie.name}“ ({von}–{bis})."
                )
        return daten


def _skala(label):
    return forms.TypedChoiceField(
        label=label,
        choices=[(i, str(i)) for i in range(1, 11)],
        coerce=int,
        widget=forms.RadioSelect,
    )


class BewertungForm(forms.ModelForm):
    produktivitaet = _skala("Wie produktiv war der Tag? (1–10)")
    zufriedenheit = _skala("Wie zufrieden bist du mit dem Tag? (1–10)")

    class Meta:
        model = Tagesbewertung
        fields = ["produktivitaet", "zufriedenheit", "schlaf_h", "notiz"]
        widgets = {
            "notiz": forms.Textarea(attrs={"rows": 3}),
            "schlaf_h": forms.NumberInput(attrs={"step": "0.5", "min": "0", "max": "24"}),
        }
        labels = {"schlaf_h": "Schlaf (Stunden, optional)"}
