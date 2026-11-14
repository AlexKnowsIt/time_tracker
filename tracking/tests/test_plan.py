from datetime import datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from tracking.models import Eintrag, Kategorie, Planblock
from tracking.plan import plan_vs_ist
from tracking.zeit import tagesgrenzen

pytestmark = pytest.mark.django_db


def lokal(*args):
    return timezone.make_aware(datetime(*args))


@pytest.fixture
def nutzer():
    return get_user_model().objects.create_user("anna", password="geheim")


@pytest.fixture
def fremder():
    return get_user_model().objects.create_user("ben", password="geheim")


@pytest.fixture
def client(client, nutzer):
    client.force_login(nutzer)
    return client


@pytest.fixture
def deepwork(nutzer):
    return Kategorie.objects.create(nutzer=nutzer, name="Deep Work", art=Kategorie.Art.DEEPWORK)


@pytest.fixture
def fremde_kategorie(fremder):
    return Kategorie.objects.create(nutzer=fremder, name="Fremd", art=Kategorie.Art.DEEPWORK)


def block(nutzer, kategorie, start, ende, titel=""):
    return Planblock.objects.create(
        nutzer=nutzer, kategorie=kategorie, start=start, ende=ende, titel=titel
    )


def daten(kategorie, start, ende, titel=""):
    return {
        "kategorie": kategorie.pk,
        "start": start.isoformat(),
        "ende": ende.isoformat(),
        "titel": titel,
    }


ZEITRAUM = {"start": "2026-11-09T00:00:00+01:00", "end": "2026-11-16T00:00:00+01:00"}


# --- plan.py ---------------------------------------------------------------


class Dummy:
    def __init__(self, art, start, ende):
        self.kategorie = type("K", (), {"art": art})()
        self.start, self.ende = start, ende


def test_plan_vs_ist_summen_und_differenz():
    beginn, ende = tagesgrenzen(lokal(2026, 11, 10).date())
    jetzt = lokal(2026, 11, 11, 12)
    plan = [Dummy("deepwork", lokal(2026, 11, 10, 9), lokal(2026, 11, 10, 11))]
    ist = [
        Dummy("deepwork", lokal(2026, 11, 10, 9), lokal(2026, 11, 10, 10, 30)),
        Dummy("pause", lokal(2026, 11, 10, 10, 30), lokal(2026, 11, 10, 10, 45)),
    ]
    zeilen = plan_vs_ist(plan, ist, beginn, ende, jetzt)
    assert [(z["art"], z["geplant"], z["erfasst"], z["differenz"]) for z in zeilen] == [
        ("deepwork", 120, 90, -30),
        ("pause", 0, 15, 15),
    ]


def test_plan_vs_ist_schneidet_an_tagesgrenze_ab():
    beginn, ende = tagesgrenzen(lokal(2026, 11, 10).date())  # 04:00 bis 04:00
    jetzt = lokal(2026, 11, 11, 12)
    # Plan 02:00-05:00 am Folgetag: nur 04:00-05:00 zählt nicht, 02:00-04:00 gehört zum Tag.
    plan = [Dummy("freizeit", lokal(2026, 11, 11, 2), lokal(2026, 11, 11, 5))]
    # Ist: begann am Vortag 03:00, nur ab 04:00 zählt; Ende 05:00.
    ist = [Dummy("freizeit", lokal(2026, 11, 10, 3), lokal(2026, 11, 10, 5))]
    (zeile,) = plan_vs_ist(plan, ist, beginn, ende, jetzt)
    assert (zeile["geplant"], zeile["erfasst"]) == (120, 60)


def test_plan_vs_ist_laufender_eintrag_zaehlt_bis_jetzt():
    beginn, ende = tagesgrenzen(lokal(2026, 11, 10).date())
    jetzt = lokal(2026, 11, 10, 10)
    ist = [Dummy("deepwork", lokal(2026, 11, 10, 9), None)]
    (zeile,) = plan_vs_ist([], ist, beginn, ende, jetzt)
    assert zeile["erfasst"] == 60


# --- JSON-Quellen ------------------------------------------------------------


def test_plan_seiten_brauchen_login(client):
    anonym = Client()
    for name in ("plan", "plan_bloecke", "plan_ist"):
        assert anonym.get(reverse(name), ZEITRAUM).status_code == 302


def test_bloecke_nutzergefiltert(client, nutzer, fremder, deepwork, fremde_kategorie):
    block(nutzer, deepwork, lokal(2026, 11, 10, 9), lokal(2026, 11, 10, 10), "Konzept")
    block(fremder, fremde_kategorie, lokal(2026, 11, 10, 9), lokal(2026, 11, 10, 10))
    block(nutzer, deepwork, lokal(2026, 12, 24, 9), lokal(2026, 12, 24, 10))  # außerhalb
    antwort = client.get(reverse("plan_bloecke"), ZEITRAUM)
    assert antwort.status_code == 200
    (ereignis,) = antwort.json()
    assert ereignis["title"] == "Deep Work: Konzept"
    assert ereignis["extendedProps"]["kategorie"] == deepwork.pk


def test_ist_nutzergefiltert_nicht_editierbar_laufend_bis_jetzt(
    client, nutzer, fremder, deepwork, fremde_kategorie
):
    Eintrag.objects.create(
        nutzer=nutzer,
        kategorie=deepwork,
        start=lokal(2026, 11, 10, 9),
        ende=lokal(2026, 11, 10, 10),
    )
    Eintrag.objects.create(
        nutzer=fremder,
        kategorie=fremde_kategorie,
        start=lokal(2026, 11, 10, 9),
        ende=lokal(2026, 11, 10, 10),
    )
    alle = client.get(reverse("plan_ist"), ZEITRAUM).json()
    assert len(alle) == 1  # nur der eigene Eintrag
    assert alle[0]["editable"] is False and alle[0]["id"].startswith("ist-")

    jetzt = timezone.now()
    Eintrag.objects.create(nutzer=nutzer, kategorie=deepwork, start=jetzt - timedelta(minutes=5))
    zeitraum = {
        "start": (jetzt - timedelta(hours=1)).isoformat(),
        "end": (jetzt + timedelta(days=1)).isoformat(),
    }
    (laufend,) = client.get(reverse("plan_ist"), zeitraum).json()
    assert datetime.fromisoformat(laufend["end"]) >= jetzt


def test_zeitraum_grenze_62_tage(client):
    von = datetime(2026, 11, 1)
    ok = {"start": von.isoformat(), "end": (von + timedelta(days=62)).isoformat()}
    zu_lang = {"start": von.isoformat(), "end": (von + timedelta(days=63)).isoformat()}
    for name in ("plan_bloecke", "plan_ist"):
        assert client.get(reverse(name), ok).status_code == 200
        assert client.get(reverse(name), zu_lang).status_code == 400
        assert client.get(reverse(name)).status_code == 400
        assert client.get(reverse(name), {"start": "x", "end": "y"}).status_code == 400
        umgekehrt = {"start": ok["end"], "end": ok["start"]}
        assert client.get(reverse(name), umgekehrt).status_code == 400


# --- Schreiben ---------------------------------------------------------------


def test_anlegen_verschieben_loeschen(client, nutzer, deepwork):
    start, ende = lokal(2026, 11, 10, 9), lokal(2026, 11, 10, 10)
    antwort = client.post(reverse("plan_neu"), daten(deepwork, start, ende, "Konzept"))
    assert antwort.status_code == 201
    pk = antwort.json()["id"]
    b = Planblock.objects.get(pk=pk)
    assert b.nutzer == nutzer and b.titel == "Konzept" and b.start == start

    neu_start, neu_ende = lokal(2026, 11, 10, 14), lokal(2026, 11, 10, 15, 30)
    antwort = client.post(
        reverse("plan_bearbeiten", args=[pk]), daten(deepwork, neu_start, neu_ende, "Konzept")
    )
    assert antwort.status_code == 200
    b.refresh_from_db()
    assert (b.start, b.ende) == (neu_start, neu_ende)

    assert client.post(reverse("plan_loeschen", args=[pk])).json() == {"ok": True}
    assert not Planblock.objects.exists()


def test_nur_post_erlaubt(client, nutzer, deepwork):
    b = block(nutzer, deepwork, lokal(2026, 11, 10, 9), lokal(2026, 11, 10, 10))
    assert client.get(reverse("plan_neu")).status_code == 405
    assert client.get(reverse("plan_loeschen", args=[b.pk])).status_code == 405
    assert Planblock.objects.count() == 1


def test_csrf_pflicht(nutzer, deepwork):
    c = Client(enforce_csrf_checks=True)
    c.force_login(nutzer)
    b = block(nutzer, deepwork, lokal(2026, 11, 10, 9), lokal(2026, 11, 10, 10))
    d = daten(deepwork, lokal(2026, 11, 11, 9), lokal(2026, 11, 11, 10))
    assert c.post(reverse("plan_neu"), d).status_code == 403
    assert c.post(reverse("plan_bearbeiten", args=[b.pk]), d).status_code == 403
    assert c.post(reverse("plan_loeschen", args=[b.pk])).status_code == 403
    assert Planblock.objects.count() == 1

    c.get(reverse("plan"))  # setzt das CSRF-Cookie
    token = c.cookies["csrftoken"].value
    assert c.post(reverse("plan_neu"), d, headers={"X-CSRFToken": token}).status_code == 201


def test_ueberlappung_abgelehnt(client, nutzer, deepwork):
    block(nutzer, deepwork, lokal(2026, 11, 10, 9), lokal(2026, 11, 10, 10))
    antwort = client.post(
        reverse("plan_neu"), daten(deepwork, lokal(2026, 11, 10, 9, 30), lokal(2026, 11, 10, 11))
    )
    assert antwort.status_code == 400
    assert "Überschneidung" in antwort.json()["fehler"]
    assert Planblock.objects.count() == 1
    # direkt anschließend ist erlaubt
    antwort = client.post(
        reverse("plan_neu"), daten(deepwork, lokal(2026, 11, 10, 10), lokal(2026, 11, 10, 11))
    )
    assert antwort.status_code == 201


def test_verschieben_auf_anderen_block_abgelehnt_eigener_block_zaehlt_nicht(
    client, nutzer, deepwork
):
    a = block(nutzer, deepwork, lokal(2026, 11, 10, 9), lokal(2026, 11, 10, 10))
    block(nutzer, deepwork, lokal(2026, 11, 10, 11), lokal(2026, 11, 10, 12))
    # überlappt nur mit sich selbst: ok
    assert (
        client.post(
            reverse("plan_bearbeiten", args=[a.pk]),
            daten(deepwork, lokal(2026, 11, 10, 9, 30), lokal(2026, 11, 10, 10, 30)),
        ).status_code
        == 200
    )
    assert (
        client.post(
            reverse("plan_bearbeiten", args=[a.pk]),
            daten(deepwork, lokal(2026, 11, 10, 10, 30), lokal(2026, 11, 10, 11, 30)),
        ).status_code
        == 400
    )


def test_ende_nach_start(client, deepwork):
    antwort = client.post(
        reverse("plan_neu"), daten(deepwork, lokal(2026, 11, 10, 10), lokal(2026, 11, 10, 9))
    )
    assert antwort.status_code == 400
    assert not Planblock.objects.exists()


def test_fremde_kategorie_und_fremder_block(client, nutzer, fremder, deepwork, fremde_kategorie):
    start, ende = lokal(2026, 11, 10, 9), lokal(2026, 11, 10, 10)
    antwort = client.post(reverse("plan_neu"), daten(fremde_kategorie, start, ende))
    assert antwort.status_code == 400  # Kategorie nicht in der nutzergefilterten Auswahl
    assert not Planblock.objects.exists()

    fremder_block = block(fremder, fremde_kategorie, start, ende)
    pfad = reverse("plan_bearbeiten", args=[fremder_block.pk])
    assert client.post(pfad, daten(deepwork, start, ende)).status_code == 404
    assert client.post(reverse("plan_loeschen", args=[fremder_block.pk])).status_code == 404
    assert Planblock.objects.get().nutzer == fremder


# --- Tagesansicht ------------------------------------------------------------


def test_tag_zeigt_plan_vs_ist_ohne_bewertung(
    client, nutzer, deepwork, django_assert_max_num_queries
):
    tag_url = reverse("tag", args=[lokal(2026, 11, 10).date()])
    assert "Plan vs. Ist" not in client.get(tag_url).content.decode()
    block(nutzer, deepwork, lokal(2026, 11, 10, 9), lokal(2026, 11, 10, 11))
    Eintrag.objects.create(
        nutzer=nutzer,
        kategorie=deepwork,
        start=lokal(2026, 11, 10, 9),
        ende=lokal(2026, 11, 10, 10),
    )
    with django_assert_max_num_queries(10):
        html = client.get(tag_url).content.decode()
    assert "Plan vs. Ist" in html and "-60 min" in html
