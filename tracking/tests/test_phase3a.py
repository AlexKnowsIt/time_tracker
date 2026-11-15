"""Phase 3a: Erfassungsfelder, Muster-Seite mit drei Stufen, API, CSV-Export, Demodaten."""

import csv
import io
import json
import re
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from tracking.forms import BewertungForm, EintragForm
from tracking.models import ApiToken, Eintrag, Kategorie, Messung, Tagesbewertung
from tracking.zeit import tagesdatum

from . import test_seiten
from .test_seiten import bewerte_tage, lokal

# Fixtures aus test_seiten mitbenutzen
client, kat, nutzer = test_seiten.client, test_seiten.kat, test_seiten.nutzer

pytestmark = pytest.mark.django_db

BASIS = {"produktivitaet": 7, "zufriedenheit": 6}


# --- Formulare und Modell ----------------------------------------------------------


@pytest.mark.parametrize("wert", ["True", "ja", "1", True])
def test_bewertung_fortschritt_ja(wert):
    form = BewertungForm({**BASIS, "fortschritt": wert})
    assert form.is_valid() and form.cleaned_data["fortschritt"] is True


@pytest.mark.parametrize("wert", ["False", "nein", "0", False])
def test_bewertung_fortschritt_nein(wert):
    form = BewertungForm({**BASIS, "fortschritt": wert})
    assert form.is_valid() and form.cleaned_data["fortschritt"] is False


def test_bewertung_fortschritt_ist_pflicht_abschalten_optional_und_1_bis_5():
    assert "fortschritt" in BewertungForm(BASIS).errors
    ok = BewertungForm({**BASIS, "fortschritt": "True", "fortschritt_notiz": "Entwurf fertig"})
    assert ok.is_valid() and ok.cleaned_data["abgeschaltet"] is None
    assert BewertungForm({**BASIS, "fortschritt": "True", "abgeschaltet": "4"}).is_valid()
    for schlecht in ("0", "6", "x"):
        assert (
            "abgeschaltet"
            in BewertungForm({**BASIS, "fortschritt": "True", "abgeschaltet": schlecht}).errors
        )


def test_abgeschaltet_check_constraint_in_der_datenbank(nutzer):
    with pytest.raises(IntegrityError), transaction.atomic():
        Tagesbewertung.objects.create(
            nutzer=nutzer,
            datum=timezone.localdate(),
            produktivitaet=5,
            zufriedenheit=5,
            abgeschaltet=6,
        )


def test_eintragform_neue_felder(nutzer, kat):
    daten = {
        "kategorie": kat["Deep Work"].pk,
        "start": "2026-11-14 09:00",
        "ende": "2026-11-14 10:00",
    }
    form = EintragForm(daten, nutzer=nutzer)
    assert form.is_valid() and form.cleaned_data["abgeschlossen"] is None
    assert form.cleaned_data["unterbrochen"] is False
    form = EintragForm({**daten, "abgeschlossen": "False", "unterbrochen": "on"}, nutzer=nutzer)
    assert form.is_valid() and form.cleaned_data["abgeschlossen"] is False
    assert form.cleaned_data["unterbrochen"] is True


def test_abschlussseite_zeigt_neue_fragen_und_speichert(client, nutzer):
    url = reverse("abschluss", args=["2026-11-14"])
    html = client.get(url).content.decode()
    assert "Hast du heute bei etwas Wichtigem Fortschritt gemacht?" in html
    assert "Wie gut konntest du nach der Arbeit abschalten?" in html
    assert client.post(url, BASIS).status_code == 200  # ohne Fortschritt keine Bewertung
    assert not Tagesbewertung.objects.exists()
    daten = {**BASIS, "fortschritt": "True", "fortschritt_notiz": "Konzept", "abgeschaltet": "4"}
    assert client.post(url, daten).status_code == 302
    b = Tagesbewertung.objects.get()
    assert (b.fortschritt, b.fortschritt_notiz, b.abgeschaltet) == (True, "Konzept", 4)
    # Bewertung ändern zeigt die gespeicherte Antwort vorausgewählt
    assert re.search(r'value="True"[^>]*checked', client.get(url).content.decode())
    tag = client.get(reverse("tag", args=["2026-11-14"])).content.decode()
    assert "Fortschritt gemacht: ja (Konzept)" in tag and "Abschalten 4/5" in tag


def test_eintrag_bearbeiten_mit_abgeschlossen_und_unterbrochen(client, nutzer, kat):
    e = Eintrag.objects.create(
        nutzer=nutzer,
        kategorie=kat["Deep Work"],
        start=lokal(timezone.localdate(), 9),
        ende=lokal(timezone.localdate(), 10),
    )
    url = reverse("eintrag_bearbeiten", args=[e.pk])
    assert "Aufgabe abgeschlossen?" in client.get(url).content.decode()
    daten = {
        "kategorie": kat["Deep Work"].pk,
        "start": f"{timezone.localdate()} 09:00",
        "ende": f"{timezone.localdate()} 10:00",
        "abgeschlossen": "True",
        "unterbrochen": "on",
    }
    assert client.post(url, daten).status_code == 302
    e.refresh_from_db()
    assert e.abgeschlossen is True and e.unterbrochen is True


def test_jetzt_wechsel_fragt_nicht_nach_abschluss(client, nutzer, kat):
    html = client.get(reverse("jetzt")).content.decode()
    assert "abgeschlossen" not in html and "unterbrochen" not in html
    client.post(reverse("start", args=[kat["Deep Work"].pk]))
    client.post(reverse("stopp"))
    e = Eintrag.objects.get()
    assert e.abgeschlossen is None and e.unterbrochen is False


# --- API und MCP ---------------------------------------------------------------------


@pytest.fixture
def api_kopf(nutzer):
    return {"HTTP_AUTHORIZATION": f"Bearer {ApiToken.erzeugen(nutzer, 'test')[1]}"}


def _post(client, pfad, daten, kopf):
    return client.post(
        f"/api/v1/{pfad}", json.dumps(daten), content_type="application/json", **kopf
    )


def test_api_bewertung_mit_neuen_feldern(client, nutzer, api_kopf):
    url = "tag/2026-11-10/bewertung"
    assert _post(client, url, BASIS, api_kopf).status_code == 400  # Fortschritt fehlt
    antwort = _post(client, url, {**BASIS, "fortschritt": True, "abgeschaltet": 3}, api_kopf)
    b = antwort.json()["bewertung"]
    assert antwort.status_code == 201
    assert (b["fortschritt"], b["abgeschaltet"], b["fortschritt_notiz"]) == (True, 3, "")
    antwort = _post(client, url, {**BASIS, "fortschritt": False, "abgeschaltet": 9}, api_kopf)
    assert antwort.status_code == 400 and "abgeschaltet" in antwort.json()["felder"]


def test_api_eintrag_nachtragen_mit_neuen_feldern(client, nutzer, kat, api_kopf):
    daten = {
        "kategorie": "Deep Work",
        "start": "2026-11-10T09:00:00",
        "ende": "2026-11-10T10:00:00",
    }
    antwort = _post(
        client, "eintraege", {**daten, "abgeschlossen": True, "unterbrochen": True}, api_kopf
    )
    e = antwort.json()["eintrag"]
    assert antwort.status_code == 201 and e["abgeschlossen"] is True and e["unterbrochen"] is True
    daten2 = {
        "kategorie": "Deep Work",
        "start": "2026-11-10T11:00:00",
        "ende": "2026-11-10T12:00:00",
    }
    e = _post(client, "eintraege", daten2, api_kopf).json()["eintrag"]
    assert e["abgeschlossen"] is None and e["unterbrochen"] is False


def test_api_muster_mit_korrelationen_und_modell(client, nutzer, kat, api_kopf):
    bewerte_tage(nutzer, kat, 20)
    daten = client.get("/api/v1/muster", **api_kopf).json()
    assert daten["zeilen"][0]["delta"] is not None and "ki" in daten["zeilen"][0]
    assert daten["korrelationen"]["fehlend"] == 10 and "ab 30" in daten["korrelationen"]["hinweis"]
    assert daten["mehrfachmodell"]["fehlend"] == 70
    for modell in (Tagesbewertung, Eintrag, Messung):
        modell.objects.all().delete()
    bewerte_tage(nutzer, kat, 95)
    daten = client.get("/api/v1/muster", **api_kopf).json()
    assert daten["korrelationen"]["zeilen"] and daten["korrelationen"]["effektives_n"] > 0
    zeile = daten["korrelationen"]["zeilen"][0]
    assert {"r", "ki", "p", "hypothese", "bh_treffer"} <= set(zeile)
    assert "keine Ursachen" in daten["korrelationen"]["hinweis"]
    assert 1 <= len(daten["mehrfachmodell"]["koeffizienten"]) <= 5
    assert "explorativ" in daten["mehrfachmodell"]["hinweis"]


def test_mcp_tools_reichen_neue_felder_durch(live_server, monkeypatch, transactional_db):
    pytest.importorskip("mcp")
    from mcp_server import server

    nutzer = get_user_model().objects.create_user("mcp")
    from tracking.services import lege_standardkategorien_an

    lege_standardkategorien_an(nutzer)
    monkeypatch.setenv("ZEITERFASSUNG_URL", live_server.url)
    monkeypatch.setenv("ZEITERFASSUNG_TOKEN", ApiToken.erzeugen(nutzer, "mcp")[1])
    text = server.eintrag_nachtragen(
        "Deep Work",
        "2026-11-10T09:00:00",
        "2026-11-10T10:00:00",
        abgeschlossen=False,
        unterbrochen=True,
    )
    assert '"abgeschlossen": false' in text and '"unterbrochen": true' in text
    text = server.tag_bewerten("2026-11-10", 6, 7, False, fortschritt_notiz="-", abgeschaltet=2)
    assert '"fortschritt": false' in text and '"abgeschaltet": 2' in text
    assert "Fehler 400" in server.tag_bewerten("2026-11-11", 6, 7, True, abgeschaltet=7)
    assert "Experimenten" in server.muster_abrufen.__doc__


# --- Muster-Seite ----------------------------------------------------------------------


def test_muster_statuszeilen_je_stufe(client, nutzer, kat):
    html = client.get(reverse("muster")).content.decode()
    assert "Noch 14 bewertete Tage bis zur ersten Auswertung" in html
    assert "bis zu den Korrelationen (ab 30 Tagen)" in html
    assert "bis zum Mehrfachmodell (ab 90 Tagen)" in html
    assert (
        "Unterschiede und Zusammenhänge, keine Ursachen. Ursachen prüfst du mit Experimenten."
        in html
    )
    bewerte_tage(nutzer, kat, 20)
    html = client.get(reverse("muster")).content.decode()
    assert "Noch 10 bewertete Tage bis zu den Korrelationen" in html
    assert "Noch 70 bewertete Tage bis zum Mehrfachmodell" in html
    assert "Cliff" in html and "deutlich" in html


def test_muster_korrelationen_und_modell_sichtbar(
    client, nutzer, kat, django_assert_max_num_queries
):
    bewerte_tage(nutzer, kat, 95)
    with django_assert_max_num_queries(12):  # kein N+1 über die Tage
        antwort = client.get(reverse("muster"))
    html = antwort.content.decode()
    assert "bis zu den Korrelationen" not in html and "bis zum Mehrfachmodell" not in html
    assert "Hypothese" in html and "Wochentagseffekte" in html and "Benjamini-Hochberg" in html
    assert "Autokorrelation" in html and "Explorativ" in html
    korr = antwort.context["korr"]
    assert korr["n"] == 95 and all("ki" in z for z in korr["zeilen"])
    assert 1 <= len(antwort.context["modell"]["koeffizienten"]) <= 5
    # Kein Kausalversprechen, keine festen Rhythmen
    for verboten in ("verursacht", "steigert den Fokus", "Pomodoro", "90 Minuten"):
        assert verboten not in html


def test_muster_ist_deterministisch(client, nutzer, kat):
    bewerte_tage(nutzer, kat, 40)
    a = client.get(reverse("muster")).context["korr"]["zeilen"]
    b = client.get(reverse("muster")).context["korr"]["zeilen"]
    assert a == b


def test_schlafschnitt_braucht_drei_werte_und_fortschritt_kommt_aus_der_bewertung(nutzer, kat):
    from tracking.views import _bewertungen, _tage_mit_merkmalen

    heute = tagesdatum(timezone.now())
    for i, schlaf in [(5, 6), (4, 7), (3, 8), (2, None), (1, 5)]:
        Tagesbewertung.objects.create(
            nutzer=nutzer,
            datum=heute - timedelta(days=i),
            produktivitaet=5,
            zufriedenheit=5,
            schlaf_h=schlaf,
            fortschritt=i % 2 == 0,
            abgeschaltet=i % 5 + 1,
        )
    tage = [heute - timedelta(days=i) for i in range(5, 0, -1)]
    bew = _bewertungen(nutzer, tage[0], tage[-1])
    ergebnis = {b["datum"]: m for b, m in _tage_mit_merkmalen(nutzer, tage, bew, timezone.now())}
    assert ergebnis[tage[0]]["schlaf_schnitt_7"] is None  # nur 1 Wert
    assert ergebnis[tage[1]]["schlaf_schnitt_7"] is None  # 2 Werte
    assert ergebnis[tage[2]]["schlaf_schnitt_7"] == pytest.approx(7)  # 6, 7, 8
    assert ergebnis[tage[4]]["schlaf_schnitt_7"] == pytest.approx(6.5)  # 6, 7, 8, 5
    assert ergebnis[tage[2]]["fortschritt"] == 0.0 and ergebnis[tage[3]]["fortschritt"] == 1.0
    assert ergebnis[tage[0]]["abgeschaltet_vortag"] is None
    assert ergebnis[tage[1]]["abgeschaltet_vortag"] == 5 % 5 + 1


# --- CSV-Export -------------------------------------------------------------------------


def _csv(antwort):
    text = antwort.content.decode("utf-8")
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text[1:]), delimiter=";"))


def test_export_tage(client, nutzer, kat):
    heute = tagesdatum(timezone.now())
    tag = heute - timedelta(days=2)
    Eintrag.objects.create(
        nutzer=nutzer, kategorie=kat["Deep Work"], start=lokal(tag, 9), ende=lokal(tag, 10, 30)
    )
    Eintrag.objects.create(
        nutzer=nutzer, kategorie=kat["Pause"], start=lokal(tag, 10, 30), ende=lokal(tag, 10, 40)
    )
    Messung.objects.create(nutzer=nutzer, zeitpunkt=lokal(tag, 9, 30), typ="wasser_ml", menge=250)
    Tagesbewertung.objects.create(
        nutzer=nutzer, datum=tag, produktivitaet=7, zufriedenheit=8, fortschritt=True,
        abgeschaltet=4, schlaf_h="7.5", notiz="=SUMME(A1)",
    )  # fmt: skip
    # Tag ohne Bewertung und Daten eines anderen Nutzers kommen nicht vor
    Eintrag.objects.create(
        nutzer=nutzer, kategorie=kat["Mails"], start=lokal(heute - timedelta(days=1), 9),
        ende=lokal(heute - timedelta(days=1), 10),
    )  # fmt: skip
    fremd = get_user_model().objects.create_user("bob")
    Tagesbewertung.objects.create(
        nutzer=fremd, datum=tag, produktivitaet=1, zufriedenheit=1, fortschritt=False
    )
    antwort = client.get(reverse("export_tage"))
    assert (
        antwort["Content-Type"].startswith("text/csv")
        and "attachment" in antwort["Content-Disposition"]
    )
    zeilen = _csv(antwort)
    kopf, daten = zeilen[0], zeilen[1:]
    assert len(daten) == 1
    z = dict(zip(kopf, daten[0], strict=True))
    assert z["datum"] == str(tag) and z["deepwork_min"] == "90" and z["pausen_anzahl"] == "1"
    assert z["beginn_min"] == "540" and z["wasser_ml"] == "250"
    assert z["schlaf_h"] == "7,5"  # Dezimalkomma
    assert z["pausen_je_deepwork_h"] == "0,67"
    assert z["produktivitaet"] == "7" and z["fortschritt"] == "1" and z["abgeschaltet"] == "4"
    assert z["notiz"] == "'=SUMME(A1)"  # Formel-Einschleusung entschärft
    assert z["letzter_kaffee_min"] == ""  # fehlt -> leer
    assert "beginn" not in kopf  # Uhrzeiten tragen die Einheit im Namen


def test_export_tage_ohne_daten_nur_kopf(client):
    zeilen = _csv(client.get(reverse("export_tage")))
    assert len(zeilen) == 1 and zeilen[0][0] == "datum"


def test_export_eintraege(client, nutzer, kat):
    tag = tagesdatum(timezone.now()) - timedelta(days=1)
    Eintrag.objects.create(
        nutzer=nutzer, kategorie=kat["Deep Work"], start=lokal(tag, 9), ende=lokal(tag, 10, 30),
        notiz="Text; mit Semikolon", abgeschlossen=True, unterbrochen=True,
    )  # fmt: skip
    Eintrag.objects.create(nutzer=nutzer, kategorie=kat["Mails"], start=lokal(tag, 11))  # läuft
    fremd = get_user_model().objects.create_user("bob")
    fremd_kat = Kategorie.objects.create(nutzer=fremd, name="Geheim", art="deepwork")
    Eintrag.objects.create(
        nutzer=fremd, kategorie=fremd_kat, start=lokal(tag, 9), ende=lokal(tag, 10)
    )
    zeilen = _csv(client.get(reverse("export_eintraege")))
    assert len(zeilen) == 3 and "Geheim" not in str(zeilen)
    erste = dict(zip(zeilen[0], zeilen[1], strict=True))
    assert erste["kategorie"] == "Deep Work" and erste["art"] == "deepwork"
    assert erste["dauer_min"] == "90" and erste["notiz"] == "Text; mit Semikolon"
    assert erste["abgeschlossen"] == "1" and erste["unterbrochen"] == "1"
    laufend = dict(zip(zeilen[0], zeilen[2], strict=True))
    assert laufend["ende"] == "" and laufend["dauer_min"] == "" and laufend["abgeschlossen"] == ""


def test_export_braucht_login(client):
    client.logout()
    for name in ("export_tage", "export_eintraege"):
        assert client.get(reverse(name)).status_code == 302


def test_einstellungen_verlinkt_export(client):
    html = client.get(reverse("einstellungen")).content.decode()
    assert reverse("export_tage") in html and reverse("export_eintraege") in html


# --- Demodaten ---------------------------------------------------------------------------


def test_demodaten_standard_und_eingebaute_zusammenhaenge(client):
    from tracking.auswertung import korrelationen
    from tracking.views import _bewertungen, _tage_mit_merkmalen

    call_command("demodaten", "demo", stdout=io.StringIO())
    demo = get_user_model().objects.get(username="demo")
    bew = Tagesbewertung.objects.filter(nutzer=demo)
    assert bew.count() >= 90  # genug für das Mehrfachmodell
    assert bew.filter(fortschritt=True).exists() and bew.filter(fortschritt=False).exists()
    assert bew.exclude(abgeschaltet=None).exists() and bew.filter(abgeschaltet=None).exists()
    assert Eintrag.objects.filter(nutzer=demo, unterbrochen=True).exists()
    assert Eintrag.objects.filter(nutzer=demo, abgeschlossen=False).exists()
    assert Messung.objects.filter(nutzer=demo, typ="kaffee").exists()

    datums = sorted(bew.values_list("datum", flat=True))
    tage = _tage_mit_merkmalen(
        demo, datums, _bewertungen(demo, datums[0], datums[-1]), timezone.now()
    )
    zufr = {z["key"]: z for z in korrelationen(tage, "zufriedenheit")["zeilen"]}
    assert zufr["fortschritt"]["r"] > 0.3 and zufr["fortschritt"]["bh_treffer"]
    prod = korrelationen(tage, "produktivitaet")["zeilen"]
    assert "anteil_unterbrochen" in {z["key"] for z in prod if z["hypothese"]}
    # Fortschritt hängt mit langen Deep-Work-Blöcken zusammen
    lang = [m["laengster_deepwork_min"] for _, m in tage if m["fortschritt"] == 1.0]
    kurz = [m["laengster_deepwork_min"] for _, m in tage if m["fortschritt"] == 0.0]
    assert sum(lang) / len(lang) > sum(kurz) / len(kurz)
    client.force_login(demo)
    html = client.get(reverse("muster")).content.decode()
    assert "Hypothese" in html and "Explorativ" in html
