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
def fokus(nutzer):
    return Kategorie.objects.create(nutzer=nutzer, name="Fokus", art=Kategorie.Art.FOKUS)


@pytest.fixture
def pause(nutzer):
    return Kategorie.objects.create(nutzer=nutzer, name="Pause", art=Kategorie.Art.PAUSE)


def test_starte_eintrag_beendet_alten(nutzer, fokus, pause):
    t0 = timezone.now()
    alt = starte_eintrag(nutzer, fokus, jetzt=t0)
    neu = starte_eintrag(nutzer, pause, jetzt=t0 + timedelta(minutes=30))
    alt.refresh_from_db()
    assert alt.ende == t0 + timedelta(minutes=30)
    assert neu.ende is None
    assert Eintrag.objects.filter(nutzer=nutzer, ende=None).count() == 1


def test_stoppe_eintrag(nutzer, fokus):
    assert stoppe_eintrag(nutzer) is None
    starte_eintrag(nutzer, fokus)
    assert stoppe_eintrag(nutzer).ende is not None


def test_zweiter_laufender_eintrag_scheitert_in_db(nutzer, fokus):
    Eintrag.objects.create(nutzer=nutzer, kategorie=fokus, start=timezone.now())
    with pytest.raises(IntegrityError), transaction.atomic():
        Eintrag.objects.create(nutzer=nutzer, kategorie=fokus, start=timezone.now())


def test_ende_vor_start_scheitert_in_db(nutzer, fokus):
    jetzt = timezone.now()
    with pytest.raises(IntegrityError), transaction.atomic():
        Eintrag.objects.create(
            nutzer=nutzer, kategorie=fokus, start=jetzt, ende=jetzt - timedelta(minutes=1)
        )


def test_score_11_scheitert(nutzer):
    heute = timezone.localdate()
    with pytest.raises(ValidationError):
        Tagesbewertung(nutzer=nutzer, datum=heute, score=11).full_clean()
    with pytest.raises(IntegrityError), transaction.atomic():
        Tagesbewertung.objects.create(nutzer=nutzer, datum=heute, score=11)


def test_eine_bewertung_pro_tag(nutzer):
    heute = timezone.localdate()
    Tagesbewertung.objects.create(nutzer=nutzer, datum=heute, score=7)
    with pytest.raises(IntegrityError), transaction.atomic():
        Tagesbewertung.objects.create(nutzer=nutzer, datum=heute, score=8)
