from datetime import datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from tracking.models import Eintrag, Kategorie, Messung, Tagesbewertung
from tracking.services import starte_eintrag

pytestmark = pytest.mark.django_db


def lokal(*args):
    return timezone.make_aware(datetime(*args))


@pytest.fixture
def nutzer():
    return get_user_model().objects.create_user("anna", password="geheim")


@pytest.fixture
def client(client, nutzer):
    client.force_login(nutzer)
    return client


@pytest.fixture
def fokus(nutzer):
    return Kategorie.objects.create(nutzer=nutzer, name="Fokus", art=Kategorie.Art.FOKUS)


@pytest.fixture
def pause(nutzer):
    return Kategorie.objects.create(nutzer=nutzer, name="Pause", art=Kategorie.Art.PAUSE)


def test_login_pflicht(client):
    client.logout()
    for name, args in [("jetzt", []), ("heute", []), ("abschluss_heute", [])]:
        antwort = client.get(reverse(name, args=args))
        assert antwort.status_code == 302
        assert antwort.url.startswith("/login/")
    assert client.post(reverse("stopp")).status_code == 302
    assert client.get(reverse("login")).status_code == 200


def test_kategorie_wechsel_beendet_alten_eintrag(client, nutzer, fokus, pause):
    alt = starte_eintrag(nutzer, fokus, jetzt=timezone.now() - timedelta(minutes=10))
    antwort = client.post(reverse("start", args=[pause.pk]))
    assert antwort.status_code == 302
    alt.refresh_from_db()
    assert alt.ende is not None
    assert Eintrag.objects.get(nutzer=nutzer, ende=None).kategorie == pause


def test_htmx_liefert_teilseite(client, fokus):
    antwort = client.post(reverse("start", args=[fokus.pk]), headers={"HX-Request": "true"})
    assert antwort.status_code == 200
    assert b"<html" not in antwort.content and b"Stopp" in antwort.content


def test_fremde_kategorie_404(client, fokus):
    fremd = Kategorie.objects.create(
        nutzer=get_user_model().objects.create_user("bob"), name="X", art="fokus"
    )
    assert client.post(reverse("start", args=[fremd.pk])).status_code == 404
    assert not Eintrag.objects.exists()


def test_wasser_knopf_legt_messung_an(client, nutzer):
    client.post(reverse("messung"), {"typ": "wasser_ml"})
    m = Messung.objects.get(nutzer=nutzer)
    assert (m.typ, m.menge) == ("wasser_ml", 250)
    assert b"250 ml" in client.get(reverse("jetzt")).content


def test_eintrag_um_zwei_uhr_gehoert_zum_vortag(client, nutzer, fokus):
    Eintrag.objects.create(
        nutzer=nutzer,
        kategorie=fokus,
        start=lokal(2026, 11, 14, 2),
        ende=lokal(2026, 11, 14, 2, 30),
    )
    vortag = client.get(reverse("tag", args=["2026-11-13"]))
    tag = client.get(reverse("tag", args=["2026-11-14"]))
    assert len(vortag.context["zeilen"]) == 1
    assert len(tag.context["zeilen"]) == 0


def test_bearbeiten_mit_ende_vor_start_abgelehnt(client, nutzer, fokus):
    e = Eintrag.objects.create(
        nutzer=nutzer, kategorie=fokus, start=lokal(2026, 11, 14, 9), ende=lokal(2026, 11, 14, 10)
    )
    daten = {
        "kategorie": fokus.pk,
        "start": "2026-11-14 11:00",
        "ende": "2026-11-14 10:00",
        "notiz": "",
    }
    antwort = client.post(reverse("eintrag_bearbeiten", args=[e.pk]), daten)
    assert antwort.status_code == 200
    assert "Ende muss nach dem Start" in antwort.content.decode()
    e.refresh_from_db()
    assert e.ende == lokal(2026, 11, 14, 10)


def test_nachtragen_und_fremde_kategorie_abgelehnt(client, nutzer, fokus):
    fremd = Kategorie.objects.create(
        nutzer=get_user_model().objects.create_user("bob"), name="X", art="fokus"
    )
    url = reverse("eintrag_neu", args=["2026-11-14"])
    daten = {"kategorie": fremd.pk, "start": "2026-11-14 09:00", "ende": "2026-11-14 10:00"}
    assert client.post(url, daten).status_code == 200
    daten["kategorie"] = fokus.pk
    assert client.post(url, daten).status_code == 302
    assert Eintrag.objects.filter(nutzer=nutzer).count() == 1


def test_tagesabschluss_anlegen_und_aktualisieren(client, nutzer):
    url = reverse("abschluss", args=["2026-11-14"])
    assert client.post(url, {"score": 7, "notiz": "gut"}).status_code == 302
    assert client.post(url, {"score": 4, "energie": 3}).status_code == 302
    b = Tagesbewertung.objects.get(nutzer=nutzer)
    assert (b.score, b.energie) == (4, 3)


def test_zusammenfassung_erst_nach_score(client, nutzer, fokus):
    Eintrag.objects.create(
        nutzer=nutzer, kategorie=fokus, start=lokal(2026, 11, 14, 9), ende=lokal(2026, 11, 14, 10)
    )
    url = reverse("tag", args=["2026-11-14"])
    assert client.get(url).context["zusammenfassung"] is None
    client.post(reverse("abschluss", args=["2026-11-14"]), {"score": 8})
    antwort = client.get(url)
    assert antwort.context["zusammenfassung"]["arten"] == [("Fokus", "1 h 00 min")]
    assert b"8/10" in antwort.content


def test_standardkategorien_idempotent(nutzer):
    call_command("standardkategorien", "anna")
    call_command("standardkategorien", "anna")
    assert Kategorie.objects.filter(nutzer=nutzer).count() == 6


def test_starte_eintrag_fremde_oder_inaktive_kategorie(nutzer, fokus):
    fremd = Kategorie.objects.create(
        nutzer=get_user_model().objects.create_user("bob"), name="X", art="fokus"
    )
    with pytest.raises(ValueError):
        starte_eintrag(nutzer, fremd)
    fokus.aktiv = False
    with pytest.raises(ValueError):
        starte_eintrag(nutzer, fokus)


def test_ueberschneidung_abgelehnt(client, nutzer, fokus, pause):
    Eintrag.objects.create(
        nutzer=nutzer, kategorie=fokus, start=lokal(2026, 11, 14, 9), ende=lokal(2026, 11, 14, 10)
    )
    url = reverse("eintrag_neu", args=["2026-11-14"])
    daten = {"kategorie": pause.pk, "start": "2026-11-14 09:30", "ende": "2026-11-14 10:30"}
    antwort = client.post(url, daten)
    assert antwort.status_code == 200
    assert "Überschneidung mit „Fokus“" in antwort.content.decode()
    # direkt anschließend ist erlaubt
    daten.update(start="2026-11-14 10:00", ende="2026-11-14 10:30")
    assert client.post(url, daten).status_code == 302
    # laufender Eintrag blockiert alles danach
    Eintrag.objects.create(nutzer=nutzer, kategorie=fokus, start=lokal(2026, 11, 14, 12))
    daten.update(start="2026-11-14 13:00", ende="2026-11-14 14:00")
    assert client.post(url, daten).status_code == 200


def test_messung_loeschen(client, nutzer):
    m = Messung.objects.create(nutzer=nutzer, zeitpunkt=timezone.now(), typ="kaffee", menge=1)
    fremd = Messung.objects.create(
        nutzer=get_user_model().objects.create_user("bob"),
        zeitpunkt=timezone.now(),
        typ="kaffee",
        menge=1,
    )
    assert client.post(reverse("messung_loeschen", args=[fremd.pk])).status_code == 404
    assert client.post(reverse("messung_loeschen", args=[m.pk])).status_code == 302
    assert (
        not Messung.objects.filter(pk=m.pk).exists()
        and Messung.objects.filter(pk=fremd.pk).exists()
    )
