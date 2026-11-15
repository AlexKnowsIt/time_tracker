from datetime import timedelta
from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone

from . import experimente
from .merkmale import schlafdauer_h
from .models import ApiToken, Eintrag, Experiment, Kategorie, Planblock, Tagesbewertung
from .zeit import tagesdatum

DT_FORMAT = "%Y-%m-%dT%H:%M"
DT_FORMATE = [DT_FORMAT, "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"]


def _dt_feld(label, required=True):
    return forms.DateTimeField(
        label=label,
        required=required,
        input_formats=DT_FORMATE,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DT_FORMAT),
    )


def finde_ueberschneidung(queryset, start, ende):
    """Erster Block im (schon nutzergefilterten) Queryset, der [start, ende) überlappt.

    Gemeinsame Regel für Einträge und Planblöcke. ende=None heißt offen; ein Block
    ohne Ende (laufender Eintrag) überlappt alles, was nach seinem Start liegt.
    """
    kandidaten = queryset.filter(Q(ende__isnull=True) | Q(ende__gt=start))
    if ende:
        kandidaten = kandidaten.filter(start__lt=ende)
    return kandidaten.select_related("kategorie").order_by("start").first()


def ueberschneidung_text(block):
    von = timezone.localtime(block.start).strftime("%d.%m. %H:%M")
    bis = timezone.localtime(block.ende).strftime("%H:%M") if block.ende else "läuft"
    return f"Überschneidung mit „{block.kategorie.name}“ ({von}–{bis})."


class PlanblockForm(forms.ModelForm):
    """Validiert Planblöcke aus dem Kalender (POST-Felder: kategorie, start, ende, titel)."""

    start = forms.DateTimeField(input_formats=DT_FORMATE + ["iso-8601"])
    ende = forms.DateTimeField(input_formats=DT_FORMATE + ["iso-8601"])

    class Meta:
        model = Planblock
        fields = ["kategorie", "start", "ende", "titel"]

    def __init__(self, *args, nutzer, **kwargs):
        super().__init__(*args, **kwargs)
        self.nutzer = nutzer
        auswahl = Q(aktiv=True)
        if self.instance.pk:
            auswahl |= Q(pk=self.instance.kategorie_id)
        self.fields["kategorie"].queryset = Kategorie.objects.filter(auswahl, nutzer=nutzer)

    def clean(self):
        daten = super().clean()
        start, ende = daten.get("start"), daten.get("ende")
        if start and ende:
            if ende <= start:
                self.add_error("ende", "Das Ende muss nach dem Start liegen.")
            else:
                kollision = finde_ueberschneidung(
                    Planblock.objects.filter(nutzer=self.nutzer).exclude(pk=self.instance.pk),
                    start,
                    ende,
                )
                if kollision:
                    raise forms.ValidationError(ueberschneidung_text(kollision))
        return daten


class JaNeinFeld(forms.TypedChoiceField):
    """Ja/Nein als bool; leer = None (nur ohne required). Nimmt auch JSON-Werte der API an."""

    _JA, _NEIN = {"true", "1", "ja"}, {"false", "0", "nein"}

    def __init__(self, **kwargs):
        super().__init__(
            choices=[("True", "Ja"), ("False", "Nein")],
            coerce=lambda wert: wert == "True",
            empty_value=None,
            **kwargs,
        )

    def to_python(self, value):
        text = str(value).strip().lower() if value is not None else ""
        value = "True" if text in self._JA else "False" if text in self._NEIN else value
        return super().to_python(value)


class EintragForm(forms.ModelForm):
    start = _dt_feld("Start")
    ende = _dt_feld("Ende")
    abgeschlossen = JaNeinFeld(
        label="Aufgabe abgeschlossen?",
        required=False,
        widget=forms.Select(choices=[("", "Keine Angabe"), ("True", "Ja"), ("False", "Nein")]),
    )

    class Meta:
        model = Eintrag
        fields = ["kategorie", "start", "ende", "notiz", "abgeschlossen", "unterbrochen"]
        widgets = {"notiz": forms.Textarea(attrs={"rows": 2})}
        labels = {"unterbrochen": "Unterbrochen (z. B. durch Nachricht oder Anruf)"}

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

    def save(self, commit=True):
        # Per Formular oder API angelegt = nachgetragen (rekonstruiert, Kahneman et al. 2004);
        # der Timer legt Einträge ohne dieses Formular an.
        if self.instance._state.adding:
            self.instance.nachgetragen = True
        return super().save(commit)

    def clean(self):
        daten = super().clean()
        start, ende = daten.get("start"), daten.get("ende")
        if start and ende and ende <= start:
            self.add_error("ende", "Das Ende muss nach dem Start liegen.")
        elif start:
            kollision = finde_ueberschneidung(
                Eintrag.objects.filter(nutzer=self.nutzer).exclude(pk=self.instance.pk),
                start,
                ende,
            )
            if kollision:
                raise forms.ValidationError(ueberschneidung_text(kollision))
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
    fortschritt = JaNeinFeld(
        label="Hast du heute bei etwas Wichtigem Fortschritt gemacht?",
        widget=forms.RadioSelect,
    )
    abgeschaltet = forms.TypedChoiceField(
        label="Wie gut konntest du nach der Arbeit abschalten? (1–5, optional)",
        choices=[(i, str(i)) for i in range(1, 6)],
        coerce=int,
        empty_value=None,
        required=False,
        widget=forms.RadioSelect,
    )

    # Nur gesetzt, wenn an dem Tag ein Experimenttag existiert (siehe abschluss-View)
    eingehalten = JaNeinFeld(
        label="Hast du dich heute an die Bedingung gehalten?",
        required=False,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Tagesbewertung
        fields = [
            "produktivitaet",
            "zufriedenheit",
            "fortschritt",
            "fortschritt_notiz",
            "abgeschaltet",
            "bettzeit",
            "aufstehzeit",
            "schlaf_h",
            "notiz",
        ]
        widgets = {
            "notiz": forms.Textarea(attrs={"rows": 3}),
            "schlaf_h": forms.NumberInput(attrs={"step": "0.5", "min": "0", "max": "24"}),
            "fortschritt_notiz": forms.TextInput(attrs={"placeholder": "Was genau? (optional)"}),
            "bettzeit": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "aufstehzeit": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }
        labels = {
            "schlaf_h": "Schlaf (Stunden, optional)",
            "fortschritt_notiz": "Fortschritt: Was?",
            "bettzeit": "Bettzeit letzte Nacht (optional)",
            "aufstehzeit": "Aufstehzeit heute (optional)",
        }
        help_texts = {
            "bettzeit": "",
            "aufstehzeit": "",
            "schlaf_h": "Leer lassen, wenn du Bett- und Aufstehzeit angibst (wird berechnet).",
        }

    def __init__(self, *args, experimenttag=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.experimenttag = experimenttag
        if experimenttag is None:
            del self.fields["eingehalten"]
        else:
            self.fields["eingehalten"].label = (
                "Hast du dich heute an die Bedingung gehalten? "
                f"(Heute: {experimenttag.get_bedingung_display()})"
            )
            self.initial["eingehalten"] = (
                None if experimenttag.eingehalten is None else str(experimenttag.eingehalten)
            )

    def clean(self):
        daten = super().clean()
        if daten.get("schlaf_h") is None and daten.get("bettzeit") and daten.get("aufstehzeit"):
            stunden = schlafdauer_h(daten["bettzeit"], daten["aufstehzeit"])
            if stunden is None:
                self.add_error(
                    "aufstehzeit",
                    "Bett- bis Aufstehzeit ergibt keine Schlafdauer von 30 Minuten bis 16 Stunden.",
                )
            else:
                daten["schlaf_h"] = Decimal(str(stunden))
        return daten


class TokenForm(forms.ModelForm):
    class Meta:
        model = ApiToken
        fields = ["name"]
        labels = {"name": "Name des Tokens"}
        widgets = {"name": forms.TextInput(attrs={"placeholder": "z. B. Claude Desktop"})}


class ExperimentForm(forms.ModelForm):
    """Neues Selbstexperiment. Die Regel besteht aus „Wenn …“ und „dann …“ (Gollwitzer & Sheeran
    2006); Hypothese, Zielgröße und Dauer sind nach dem Start fest."""

    zielgroesse = forms.ChoiceField(
        label="Woran messen wir es?",
        choices=[(k, v[0]) for k, v in experimente.ZIELE.items()],
    )
    start = forms.DateField(
        label="Start", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    blocklaenge = forms.IntegerField(
        label="Tage je Block bzw. Phase",
        required=False,
        min_value=1,
        max_value=28,
        help_text="Nur bei „Blöcke“ und „ABAB“. Bei ABAB ist die Dauer 4 × Phasenlänge.",
    )
    dauer_tage = forms.IntegerField(label="Dauer in Tagen", required=False, min_value=1)
    bedingung_a = forms.CharField(
        label="Bedingung A (Vergleich)", max_length=200, required=False, initial="Wie immer"
    )

    class Meta:
        model = Experiment
        fields = [
            "titel",
            "hypothese",
            "regel_wenn",
            "regel_dann",
            "bedingung_a",
            "design",
            "blocklaenge",
            "dauer_tage",
            "zielgroesse",
            "start",
        ]
        widgets = {"hypothese": forms.Textarea(attrs={"rows": 2})}
        labels = {
            "titel": "Titel",
            "hypothese": "Hypothese (was erwartest du?)",
            "regel_wenn": "Wenn …",
            "regel_dann": "… dann",
            "bedingung_a": "Bedingung A (Vergleich)",
            "design": "Ablauf",
        }
        help_texts = {
            "hypothese": "",
            "regel_wenn": "z. B. „es 14 Uhr ist“",
            "regel_dann": "z. B. „trinke ich keinen Kaffee mehr“",
        }

    def __init__(self, *args, nutzer, **kwargs):
        super().__init__(*args, **kwargs)
        self.nutzer = nutzer
        self.fields["start"].initial = tagesdatum(timezone.now())

    def clean_bedingung_a(self):
        return self.cleaned_data["bedingung_a"].strip() or "Wie immer"

    def clean_regel_wenn(self):
        return self._satzteil("regel_wenn", ("wenn",))

    def clean_regel_dann(self):
        return self._satzteil("regel_dann", ("dann",))

    def _satzteil(self, name, praefixe):
        text = self.cleaned_data[name].strip().rstrip(".,;: ")
        for praefix in praefixe:  # „Wenn …“ bzw. „dann …“ nicht doppelt schreiben
            if text.lower().startswith(praefix + " "):
                text = text[len(praefix) :].strip()
        if len(text) < 3:
            raise forms.ValidationError("Bitte einen Satzteil schreiben.")
        return text

    def clean_start(self):
        start = self.cleaned_data["start"]
        heute = tagesdatum(timezone.now())
        if not heute <= start <= heute + timedelta(days=14):
            raise forms.ValidationError("Der Start liegt heute oder in den nächsten 14 Tagen.")
        return start

    def clean(self):
        daten = super().clean()
        design = daten.get("design")
        if not design:
            return daten
        blocklaenge = daten.get("blocklaenge") or (1 if design == experimente.TAGEWEISE else None)
        if design == experimente.TAGEWEISE:
            blocklaenge = 1
        dauer = daten.get("dauer_tage")
        if design == experimente.ABAB and blocklaenge:
            dauer = 4 * blocklaenge  # vier Phasen: Dauer ergibt sich
        if blocklaenge is None:
            self.add_error("blocklaenge", "Bitte die Tage je Block bzw. Phase angeben.")
        else:
            fehler = experimente.design_fehler(design, dauer, blocklaenge)
            if fehler:
                self.add_error("dauer_tage", fehler)
        daten["blocklaenge"], daten["dauer_tage"] = blocklaenge, dauer
        if (
            not self.errors
            and Experiment.objects.filter(
                nutzer=self.nutzer, status=Experiment.Status.LAEUFT
            ).exists()
        ):
            raise forms.ValidationError(
                "Es läuft schon ein Experiment. Erst beenden oder abbrechen."
            )
        return daten


class AbbruchForm(forms.Form):
    vermerk = forms.CharField(
        label="Warum brichst du ab?",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Pflicht: Der Vermerk bleibt am Experiment stehen.",
    )

    def clean_vermerk(self):
        text = self.cleaned_data["vermerk"].strip()
        if not text:
            raise forms.ValidationError("Bitte einen Vermerk schreiben.")
        return text
