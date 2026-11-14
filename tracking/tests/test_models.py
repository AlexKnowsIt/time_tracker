from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from tracking.models import Eintrag, Kategorie, Tagesbewertung
from tracking.services import starte_eintrag, stoppe_eintrag

pytestmark = pytest.mark.django_db


@pytest.fixture
def nutzer():
    return get_user_model().objects.create_user("anna")


@pytest.fixture
def deepwork(nutzer):
    return Kategorie.objects.create(nutzer=nutzer, name="Deep Work", art=Kategorie.Art.DEEPWORK)


@pytest.fixture
def pause(nutzer):
    return Kategorie.objects.create(nutzer=nutzer, name="Pause", art=Kategorie.Art.PAUSE)


def test_starte_eintrag_beendet_alten(nutzer, deepwork, pause):
    t0 = timezone.now()
    alt = starte_eintrag(nutzer, deepwork, jetzt=t0)
    neu = starte_eintrag(nutzer, pause, jetzt=t0 + timedelta(minutes=30))
    alt.refresh_from_db()
    assert alt.ende == t0 + timedelta(minutes=30)
    assert neu.ende is None
    assert Eintrag.objects.filter(nutzer=nutzer, ende=None).count() == 1


def test_stoppe_eintrag(nutzer, deepwork):
    assert stoppe_eintrag(nutzer) is None
    starte_eintrag(nutzer, deepwork)
    assert stoppe_eintrag(nutzer).ende is not None


def test_zweiter_laufender_eintrag_scheitert_in_db(nutzer, deepwork):
    Eintrag.objects.create(nutzer=nutzer, kategorie=deepwork, start=timezone.now())
    with pytest.raises(IntegrityError), transaction.atomic():
        Eintrag.objects.create(nutzer=nutzer, kategorie=deepwork, start=timezone.now())


def test_ende_vor_start_scheitert_in_db(nutzer, deepwork):
    jetzt = timezone.now()
    with pytest.raises(IntegrityError), transaction.atomic():
        Eintrag.objects.create(
            nutzer=nutzer, kategorie=deepwork, start=jetzt, ende=jetzt - timedelta(minutes=1)
        )


@pytest.mark.parametrize("feld", ["produktivitaet", "zufriedenheit"])
@pytest.mark.parametrize("wert", [0, 11])
def test_score_ausserhalb_1_bis_10_scheitert(nutzer, feld, wert):
    daten = {"produktivitaet": 5, "zufriedenheit": 5, feld: wert}
    heute = timezone.localdate()
    with pytest.raises(ValidationError):
        Tagesbewertung(nutzer=nutzer, datum=heute, **daten).full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        Tagesbewertung.objects.create(nutzer=nutzer, datum=heute, **daten)


def test_eine_bewertung_pro_tag(nutzer):
    heute = timezone.localdate()
    Tagesbewertung.objects.create(nutzer=nutzer, datum=heute, produktivitaet=7, zufriedenheit=6)
    with pytest.raises(IntegrityError), transaction.atomic():
        Tagesbewertung.objects.create(nutzer=nutzer, datum=heute, produktivitaet=8, zufriedenheit=8)
