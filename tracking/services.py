"""Timer-Logik: höchstens ein laufender Eintrag pro Nutzer."""

from django.db import transaction
from django.utils import timezone

from .models import Eintrag, Kategorie


def stoppe_eintrag(nutzer, jetzt=None):
    """Beendet den laufenden Eintrag und gibt ihn zurück (None, wenn keiner lief)."""
    jetzt = jetzt or timezone.now()
    with transaction.atomic():
        eintrag = Eintrag.objects.select_for_update().filter(nutzer=nutzer, ende=None).first()
        if eintrag:
            eintrag.ende = jetzt
            eintrag.save(update_fields=["ende"])
        return eintrag


def starte_eintrag(nutzer, kategorie, jetzt=None):
    """Beendet den laufenden Eintrag und startet einen neuen in der Kategorie."""
    if kategorie.nutzer_id != nutzer.pk or not kategorie.aktiv:
        raise ValueError("Kategorie gehört nicht zum Nutzer oder ist nicht aktiv.")
    jetzt = jetzt or timezone.now()
    with transaction.atomic():
        stoppe_eintrag(nutzer, jetzt)
        return Eintrag.objects.create(nutzer=nutzer, kategorie=kategorie, start=jetzt)


STANDARDKATEGORIEN = [
    ("Deep Work", Kategorie.Art.DEEPWORK, "#2a5db0"),
    ("Mails", Kategorie.Art.SHALLOWWORK, "#6b4fa0"),
    ("Meetings", Kategorie.Art.SHALLOWWORK, "#8a5a00"),
    ("Organisation", Kategorie.Art.ORGANISATION, "#2a8a8a"),
    ("Pause", Kategorie.Art.PAUSE, "#1d7a4d"),
    ("Sport", Kategorie.Art.FREIZEIT, "#b3402a"),
    ("Freizeit", Kategorie.Art.FREIZEIT, "#5c6670"),
]


def lege_standardkategorien_an(nutzer):
    """Idempotent. Gibt die Anzahl neu angelegter Kategorien zurück."""
    neu = 0
    for name, art, farbe in STANDARDKATEGORIEN:
        _, angelegt = Kategorie.objects.get_or_create(
            nutzer=nutzer, name=name, defaults={"art": art, "farbe": farbe}
        )
        neu += angelegt
    return neu
