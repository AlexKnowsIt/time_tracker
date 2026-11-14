"""Timer-Logik: höchstens ein laufender Eintrag pro Nutzer."""

from django.db import transaction
from django.utils import timezone

from .models import Eintrag


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
