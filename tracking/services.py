"""Timer-Logik: höchstens ein laufender Eintrag pro Nutzer."""

import random
import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from . import experimente
from .models import Eintrag, Experiment, ExperimentTag, Kategorie


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


# --- Selbstexperimente ------------------------------------------------------------------


def beende_abgelaufene_experimente(nutzer, heute):
    """Setzt laufende Experimente, deren letzter Tag vor ``heute`` liegt, auf „beendet“."""
    for e in Experiment.objects.filter(nutzer=nutzer, status=Experiment.Status.LAEUFT).annotate(
        letzter=Max("tage__datum")
    ):
        if e.letzter is None or e.letzter < heute:
            e.status = Experiment.Status.BEENDET
            e.save(update_fields=["status"])


def laufendes_experiment(nutzer, heute):
    """Das laufende Experiment des Nutzers (None, wenn keines läuft); schließt Abgelaufene ab."""
    beende_abgelaufene_experimente(nutzer, heute)
    return Experiment.objects.filter(nutzer=nutzer, status=Experiment.Status.LAEUFT).first()


def starte_experiment(nutzer, *, seed=None, **felder):
    """Legt das Experiment samt Zuweisung aller Tage an (einmal, danach unveränderlich).

    ``felder``: titel, hypothese, regel_wenn, regel_dann, bedingung_a, design, blocklaenge,
    zielgroesse, start, dauer_tage. Höchstens ein laufendes Experiment pro Nutzer (ValueError).
    """
    seed = secrets.randbelow(2**31) if seed is None else seed
    rng = random.Random(seed)
    bedingungen = experimente.zuweisung(
        felder["design"], felder["dauer_tage"], felder["blocklaenge"], rng
    )
    try:
        with transaction.atomic():
            experiment = Experiment.objects.create(nutzer=nutzer, seed=seed, **felder)
            ExperimentTag.objects.bulk_create(
                ExperimentTag(
                    experiment=experiment,
                    datum=experiment.start + timedelta(days=i),
                    bedingung=bedingung,
                )
                for i, bedingung in enumerate(bedingungen)
            )
    except IntegrityError:
        raise ValueError("Es läuft schon ein Experiment. Erst beenden oder abbrechen.") from None
    return experiment


def breche_experiment_ab(experiment, vermerk):
    """Abbruch nur mit Vermerk (was hat nicht funktioniert?)."""
    vermerk = (vermerk or "").strip()
    if not vermerk:
        raise ValueError("Ein Abbruch braucht einen Vermerk.")
    if experiment.status != Experiment.Status.LAEUFT:
        raise ValueError("Nur ein laufendes Experiment lässt sich abbrechen.")
    experiment.status = Experiment.Status.ABGEBROCHEN
    experiment.abbruch_vermerk = vermerk
    experiment.save(update_fields=["status", "abbruch_vermerk"])


def bestaetige_experimenttag(nutzer, datum, eingehalten):
    """Trägt ein, ob die Bedingung des Tages eingehalten wurde. None, wenn es keinen
    Experimenttag dieses Nutzers an dem Datum gibt."""
    tag = (
        ExperimentTag.objects.filter(experiment__nutzer=nutzer, datum=datum)
        .exclude(experiment__status=Experiment.Status.ABGEBROCHEN)
        .first()
    )
    if tag is None:
        return None
    tag.eingehalten = eingehalten
    tag.save(update_fields=["eingehalten"])
    return tag
