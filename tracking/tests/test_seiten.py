import json
import re
from datetime import datetime, time, timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone

from tracking.models import Eintrag, Kategorie, Messung, Tagesbewertung
from tracking.services import lege_standardkategorien_an
from tracking.zeit import tagesdatum

pytestmark = pytest.mark.django_db


def lokal(tag, h, m=0):
    return timezone.make_aware(datetime.combine(tag, time(h, m)))


@pytest.fixture
def nutzer():
    return get_user_model().objects.create_user("anna", password="geheim")


@pytest.fixture
def client(client, nutzer):
    client.force_login(nutzer)
    return client


@pytest.fixture
def kat(nutzer):
    lege_standardkategorien_an(nutzer)
    return {k.name: k for k in Kategorie.objects.filter(nutzer=nutzer)}


def bewerte_tage(nutzer, kat, anzahl):
    """Je Tag Deep Work (länger an guten Tagen) und eine Bewertung; Tage bis gestern."""
    heute = tagesdatum(timezone.now())
    for i in range(1, anzahl + 1):
        tag = heute - timedelta(days=i)
        laenge = 30 + 10 * (i % 9)
        Eintrag.objects.create(
            nutzer=nutzer,
            kategorie=kat["Deep Work"],
            start=lokal(tag, 9),
            ende=lokal(tag, 9) + timedelta(minutes=laenge),
        )
        Eintrag.objects.create(
            nutzer=nutzer,
            kategorie=kat["Pause"],
            start=lokal(tag, 11),
            ende=lokal(tag, 11, 15),
        )
        Messung.objects.create(
            nutzer=nutzer, zeitpunkt=lokal(tag, 10), typ="wasser_ml", menge=250 + 50 * (i % 5)
        )
        Tagesbewertung.objects.create(
            nutzer=nutzer, datum=tag, produktivitaet=1 + i % 9, zufriedenheit=10 - i % 9
        )


def test_muster_unter_min_tage(client, nutzer, kat):
    bewerte_tage(nutzer, kat, 12)
    antwort = client.get(reverse("muster"))
    assert antwort.status_code == 200
    assert "Noch 2 bewertete Tage bis zur ersten Auswertung" in antwort.content.decode()
    assert "ergebnis" not in antwort.context


def test_muster_ohne_bewertung_zeigt_alle_fehlenden_tage(client):
    assert "Noch 14 bewertete Tage" in client.get(reverse("muster")).content.decode()


def test_muster_ueber_min_tage_und_zielgroesse_umschalten(client, nutzer, kat):
    bewerte_tage(nutzer, kat, 18)
    antwort = client.get(reverse("muster"))
    html = antwort.content.decode()
    assert antwort.context["ziel"] == "produktivitaet"
    assert antwort.context["ergebnis"]["n"] == 18
    assert "Unterschiede, keine Ursachen." in html
    assert "Ø gute" in html and "Deep Work gesamt" in html
    zeilen = antwort.context["ergebnis"]["zeilen"]
    assert zeilen and zeilen == sorted(zeilen, key=lambda z: -abs(z["effekt"]))
    # Zielgröße wechseln: Gegenläufig bewertet, also kehrt sich der Effekt um
    zufr = client.get(reverse("muster"), {"ziel": "zufriedenheit"})
    assert zufr.context["ziel"] == "zufriedenheit" and "Ø Zufriedenheit" in zufr.content.decode()
    dw = lambda a: next(z for z in a.context["ergebnis"]["zeilen"] if z["key"] == "deepwork_min")  # noqa: E731
    assert dw(antwort)["effekt"] * dw(zufr)["effekt"] < 0
    # Unbekannte Zielgröße fällt auf Produktivität zurück
    assert client.get(reverse("muster"), {"ziel": "x"}).context["ziel"] == "produktivitaet"


def test_muster_ist_nutzergefiltert(client, nutzer, kat):
    fremd = get_user_model().objects.create_user("bob")
    lege_standardkategorien_an(fremd)
    fremd_kat = {k.name: k for k in Kategorie.objects.filter(nutzer=fremd)}
    bewerte_tage(fremd, fremd_kat, 20)
    assert "Noch 14 bewertete Tage" in client.get(reverse("muster")).content.decode()


def test_vortag_kontext_nur_wenn_vortag_bewertet(client, nutzer, kat):
    bewerte_tage(nutzer, kat, 18)
    zeilen = client.get(reverse("muster")).context["ergebnis"]["zeilen"]
    assert "produktivitaet_vortag" in {z["key"] for z in zeilen}


def test_woche_zeitleisten_und_scores(client, nutzer, kat, django_assert_max_num_queries):
    heute = tagesdatum(timezone.now())
    montag = heute - timedelta(days=heute.weekday())
    for i in range(7):
        tag = montag + timedelta(days=i)
        for h, name in [(8, "Deep Work"), (10, "Mails"), (11, "Pause")]:
            Eintrag.objects.create(
                nutzer=nutzer,
                kategorie=kat[name],
                start=lokal(tag, h),
                ende=lokal(tag, h, 45),
            )
    Tagesbewertung.objects.create(nutzer=nutzer, datum=montag, produktivitaet=7, zufriedenheit=4)
    with django_assert_max_num_queries(6):
        antwort = client.get(reverse("woche", args=[montag + timedelta(days=3)]))
    assert antwort.status_code == 200
    tage = antwort.context["tage"]
    assert len(tage) == 7 and antwort.context["montag"] == montag
    assert all(t["zeitleiste"] for t in tage)
    html = antwort.content.decode()
    assert "7/10" in html and "4/10" in html
    assert tage[0]["deepwork"] == "45 min"
    # Statistik erst nach Bewertung
    assert tage[1]["bewertung"] is None and tage[1]["deepwork"] is None
    assert reverse("woche", args=[montag - timedelta(days=7)]) in html
    assert reverse("woche", args=[montag + timedelta(days=7)]) in html


def test_woche_aktuell_und_fremde_daten(client, nutzer, kat):
    fremd = get_user_model().objects.create_user("bob")
    lege_standardkategorien_an(fremd)
    tag = tagesdatum(timezone.now())
    Eintrag.objects.create(
        nutzer=fremd,
        kategorie=Kategorie.objects.get(nutzer=fremd, name="Mails"),
        start=lokal(tag, 9),
        ende=lokal(tag, 10),
    )
    antwort = client.get(reverse("woche_aktuell"))
    assert antwort.status_code == 200
    assert not any(t["zeitleiste"] for t in antwort.context["tage"])
    assert client.get(reverse("woche", args=["2026-02-30"])).status_code == 404


def test_demodaten_bricht_bei_vorhandenen_daten_ab(nutzer, kat):
    Eintrag.objects.create(
        nutzer=nutzer,
        kategorie=kat["Mails"],
        start=timezone.now() - timedelta(hours=2),
        ende=timezone.now() - timedelta(hours=1),
    )
    with pytest.raises(CommandError, match="schon Daten"):
        call_command("demodaten", "anna")
    assert Tagesbewertung.objects.count() == 0 and Eintrag.objects.count() == 1


@pytest.mark.parametrize("vorhanden", [Messung, Tagesbewertung])
def test_demodaten_bricht_auch_bei_messung_oder_bewertung_ab(nutzer, vorhanden):
    if vorhanden is Messung:
        Messung.objects.create(nutzer=nutzer, zeitpunkt=timezone.now(), typ="kaffee", menge=1)
    else:
        Tagesbewertung.objects.create(
            nutzer=nutzer, datum=timezone.localdate(), produktivitaet=5, zufriedenheit=5
        )
    with pytest.raises(CommandError):
        call_command("demodaten", "anna")


def test_demodaten_erfolg_legt_nutzer_an_und_ist_deterministisch(client):
    ausgabe = StringIO()
    call_command("demodaten", "demo", "--tage", "28", stdout=ausgabe)
    call_command("demodaten", "demo2", "--tage", "28", stdout=StringIO())
    demo = get_user_model().objects.get(username="demo")
    assert demo.check_password("demo") and "Passwort: demo" in ausgabe.getvalue()
    gestern = tagesdatum(timezone.now()) - timedelta(days=1)
    bew = list(Tagesbewertung.objects.filter(nutzer=demo).order_by("datum"))
    assert 15 <= len(bew) <= 20 and all(b.datum.weekday() < 5 for b in bew)
    assert bew[-1].datum <= gestern and Eintrag.objects.filter(nutzer=demo, ende=None).count() == 0
    assert all(1 <= b.produktivitaet <= 10 and 1 <= b.zufriedenheit <= 10 for b in bew)
    zwei = Tagesbewertung.objects.filter(nutzer__username="demo2").order_by("datum")
    assert [(b.datum, b.produktivitaet, b.zufriedenheit) for b in bew] == [
        (b.datum, b.produktivitaet, b.zufriedenheit) for b in zwei
    ]
    # keine Überlappung, Start zwischen 7:30 und 9:30 am ersten Eintrag des Tages
    eintraege = list(Eintrag.objects.filter(nutzer=demo).order_by("start"))
    assert all(a.ende <= b.start for a, b in zip(eintraege, eintraege[1:], strict=False))
    ersten = {}
    for e in eintraege:
        ersten.setdefault(tagesdatum(e.start), timezone.localtime(e.start))
    assert all(7 * 60 + 30 <= z.hour * 60 + z.minute <= 9 * 60 + 30 for z in ersten.values())
    assert Messung.objects.filter(nutzer=demo, typ="wasser_ml").exists()
    # Muster funktioniert auf den Demodaten
    client.force_login(demo)
    assert "Ø gute" in client.get(reverse("muster")).content.decode()


def _json_script(html, kennung):
    treffer = re.search(
        rf'<script id="{kennung}" type="application/json">(.*?)</script>', html, re.S
    )
    assert treffer, f"json_script {kennung} fehlt"
    return json.loads(treffer.group(1))


def test_woche_enthaelt_diagrammdaten(client, nutzer, kat):
    heute = tagesdatum(timezone.now())
    montag = heute - timedelta(days=heute.weekday())
    for name, h, minuten in [("Deep Work", 8, 90), ("Pause", 10, 30)]:
        Eintrag.objects.create(
            nutzer=nutzer,
            kategorie=kat[name],
            start=lokal(montag, h),
            ende=lokal(montag, h) + timedelta(minutes=minuten),
        )
    antwort = client.get(reverse("woche", args=[montag]))
    daten = _json_script(antwort.content.decode(), "woche-daten")
    assert len(daten["tage"]) == 7 and daten["tage"][0] == montag.isoformat()
    arten = {a["key"]: a["minuten"] for a in daten["arten"]}
    assert arten["deepwork"][0] == 90 and arten["pause"][0] == 30 and arten["deepwork"][1] == 0
    assert "Deep Work 1 h 30 min" in daten["text"]
    # Ohne Einträge gibt es kein Diagramm, die Seite funktioniert trotzdem.
    leer = client.get(reverse("woche", args=[montag - timedelta(days=70)]))
    assert leer.status_code == 200 and "woche-daten" not in leer.content.decode()


def test_muster_enthaelt_verlaufsdaten(client, nutzer, kat):
    bewerte_tage(nutzer, kat, 18)
    daten = _json_script(client.get(reverse("muster")).content.decode(), "verlauf-daten")
    assert len(daten["tage"]) == 90
    for schluessel in ("produktivitaet", "zufriedenheit"):
        assert len(daten[schluessel]) == 90 and len(daten["schnitt_" + schluessel]) == 90
    assert sum(w is not None for w in daten["produktivitaet"]) == 18
    assert daten["tage"][-1] == tagesdatum(timezone.now()).isoformat()
    # gleitender 7-Tage-Schnitt liegt innerhalb der Tageswerte (1..10)
    assert all(1 <= w <= 10 for w in daten["schnitt_produktivitaet"] if w is not None)
    assert "7-Tage-Schnitt" in daten["text"]
    # Unter zwei bewerteten Tagen kein Diagramm
    Tagesbewertung.objects.all().delete()
    assert "verlauf-daten" not in client.get(reverse("muster")).content.decode()
