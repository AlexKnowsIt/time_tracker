import json
from datetime import datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from tracking.models import ApiToken, Eintrag, Kategorie, Messung, Planblock, Tagesbewertung
from tracking.services import lege_standardkategorien_an
from tracking.zeit import tagesdatum

from .test_seiten import bewerte_tage

pytestmark = pytest.mark.django_db

API = "/api/v1/"


def lokal(*args):
    return timezone.make_aware(datetime(*args))


@pytest.fixture
def nutzer():
    return get_user_model().objects.create_user("anna", password="geheim")


@pytest.fixture
def token(nutzer):
    return ApiToken.erzeugen(nutzer, "test")[1]


@pytest.fixture
def kat(nutzer):
    lege_standardkategorien_an(nutzer)
    return {k.name: k for k in Kategorie.objects.filter(nutzer=nutzer)}


class Anfragen:
    def __init__(self, client, token):
        self.client, self.token = client, token

    def _kopf(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"} if self.token else {}

    def get(self, pfad, **abfrage):
        return self.client.get(API + pfad, abfrage, **self._kopf())

    def post(self, pfad, daten=None, roh=None):
        body = roh if roh is not None else json.dumps(daten if daten is not None else {})
        return self.client.post(API + pfad, body, content_type="application/json", **self._kopf())

    def delete(self, pfad):
        return self.client.delete(API + pfad, **self._kopf())


@pytest.fixture
def api(client, token):
    return Anfragen(client, token)


# --- Auth ------------------------------------------------------------------------


@pytest.mark.parametrize("kopf", [None, "Bearer zt_falsch", "Basic abc", "Bearer "])
def test_ohne_oder_falsches_token_401(client, kopf):
    zusatz = {"HTTP_AUTHORIZATION": kopf} if kopf is not None else {}
    antwort = client.get(API + "jetzt", **zusatz)
    assert antwort.status_code == 401
    assert "fehler" in antwort.json()


def test_session_login_allein_reicht_nicht(client, nutzer):
    client.force_login(nutzer)
    assert client.get(API + "jetzt").status_code == 401
    assert client.post(API + "stopp", "{}", content_type="application/json").status_code == 401


def test_post_ohne_csrf_token_mit_bearer_geht(client, token):
    # Test-Client erzwingt CSRF nur mit enforce_csrf_checks; hier explizit geprüft.
    from django.test import Client

    c = Client(enforce_csrf_checks=True)
    antwort = c.post(
        API + "stopp", "{}", content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}"
    )
    assert antwort.status_code == 200


def test_widerrufenes_token_401(api, nutzer):
    assert api.get("jetzt").status_code == 200
    ApiToken.objects.filter(nutzer=nutzer).delete()
    assert api.get("jetzt").status_code == 401


def test_token_nur_als_hash_gespeichert(nutzer, token):
    gespeichert = ApiToken.objects.get(nutzer=nutzer)
    assert token.startswith("zt_")
    assert token not in (gespeichert.token_hash, gespeichert.name)
    assert gespeichert.token_hash == ApiToken.hash_von(token) and len(gespeichert.token_hash) == 64


def test_zuletzt_genutzt_hoechstens_einmal_pro_minute(api, nutzer):
    api.get("jetzt")
    erste = ApiToken.objects.get(nutzer=nutzer).zuletzt_genutzt
    assert erste is not None
    api.get("jetzt")
    assert ApiToken.objects.get(nutzer=nutzer).zuletzt_genutzt == erste
    ApiToken.objects.update(zuletzt_genutzt=erste - timedelta(minutes=2))
    api.get("jetzt")
    assert ApiToken.objects.get(nutzer=nutzer).zuletzt_genutzt > erste - timedelta(minutes=1)


def test_falsche_methode_405_und_unbekannter_pfad_404(api):
    antwort = api.client.get(API + "start", HTTP_AUTHORIZATION=f"Bearer {api.token}")
    assert antwort.status_code == 405 and antwort["Allow"] == "POST"
    assert api.get("gibtsnicht").status_code == 404
    assert api.get("tag/2026-13-45").status_code == 404
    assert api.get("gibtsnicht").json()["fehler"]


# --- Body ------------------------------------------------------------------------


def test_body_zu_gross_und_ungueltig(api):
    assert api.post("start", roh="x" * 20_000).status_code == 413
    assert api.post("start", roh="{kaputt").status_code == 400
    assert api.post("start", roh="[1, 2]").status_code == 400
    assert api.post("eintraege", {"kategorie": {"a": 1}}).status_code == 400


# --- Jetzt, Timer, Messung --------------------------------------------------------


def test_jetzt_liefert_kategorien_und_summen(api, nutzer, kat):
    Messung.objects.create(nutzer=nutzer, zeitpunkt=timezone.now(), typ="wasser_ml", menge=300)
    Kategorie.objects.create(nutzer=nutzer, name="Alt", art="pause", aktiv=False)
    daten = api.get("jetzt").json()
    assert daten["laufend"] is None
    assert {k["name"] for k in daten["kategorien"]} == set(kat)
    assert set(daten["kategorien"][0]) == {"id", "name", "art"}
    assert daten["heute"]["wasser_ml"] == 300 and daten["heute"]["kaffee"] == 0


def test_start_per_name_und_id_und_stopp(api, nutzer, kat):
    antwort = api.post("start", {"kategorie": "deep work"})  # Groß-/Kleinschreibung egal
    assert antwort.status_code == 201
    assert antwort.json()["eintrag"]["kategorie"]["name"] == "Deep Work"
    antwort = api.post("start", {"kategorie": kat["Pause"].pk})
    assert antwort.status_code == 201
    assert Eintrag.objects.filter(nutzer=nutzer, ende=None).get().kategorie == kat["Pause"]
    assert Eintrag.objects.filter(nutzer=nutzer).count() == 2
    assert api.get("jetzt").json()["laufend"]["kategorie"]["name"] == "Pause"
    gestoppt = api.post("stopp").json()["eintrag"]
    assert gestoppt["ende"] and not gestoppt["laeuft"]
    assert api.post("stopp").json()["eintrag"] is None


def test_start_fehler(api, nutzer, kat):
    fremd = Kategorie.objects.create(
        nutzer=get_user_model().objects.create_user("bob"), name="Fremd", art="deepwork"
    )
    inaktiv = Kategorie.objects.create(nutzer=nutzer, name="Alt", art="pause", aktiv=False)
    for wert in (fremd.pk, "fremd", inaktiv.pk, "Gibt es nicht"):
        antwort = api.post("start", {"kategorie": wert})
        assert antwort.status_code == 404, wert
        assert "kategorie" in antwort.json()["felder"]
    assert api.post("start", {}).status_code == 400
    assert not Eintrag.objects.exists()


def test_messung_defaults_und_grenzen(api, nutzer):
    assert api.post("messung", {"typ": "wasser_ml"}).json()["messung"]["menge"] == 250
    assert api.post("messung", {"typ": "kaffee"}).json()["messung"]["menge"] == 1
    antwort = api.post("messung", {"typ": "wasser_ml", "menge": 500})
    assert antwort.status_code == 201 and antwort.json()["heute"] == {"wasser_ml": 750, "kaffee": 1}
    for schlecht in (
        {"typ": "bier"},
        {"typ": "wasser_ml", "menge": 0},
        {"typ": "kaffee", "menge": 5001},
        {"typ": "kaffee", "menge": "2"},
        {"typ": "kaffee", "menge": True},
    ):
        assert api.post("messung", schlecht).status_code == 400, schlecht
    assert Messung.objects.count() == 3


# --- Nachtragen ------------------------------------------------------------------


def test_nachtragen_mit_offset_und_naiv(api, nutzer, kat):
    antwort = api.post(
        "eintraege",
        {"kategorie": "Mails", "start": "2026-11-14T09:00:00+01:00", "ende": "2026-11-14T10:00:00"},
    )
    assert antwort.status_code == 201
    e = Eintrag.objects.get()
    assert (
        e.nutzer == nutzer
        and e.start == lokal(2026, 11, 14, 9)
        and e.ende == lokal(2026, 11, 14, 10)
    )
    assert antwort.json()["eintrag"]["dauer_min"] == 60


def test_nachtragen_ueberschneidung_400_mit_feldfehlern(api, nutzer, kat):
    Eintrag.objects.create(
        nutzer=nutzer,
        kategorie=kat["Deep Work"],
        start=lokal(2026, 11, 14, 9),
        ende=lokal(2026, 11, 14, 10),
    )
    antwort = api.post(
        "eintraege",
        {"kategorie": "Mails", "start": "2026-11-14T09:30:00", "ende": "2026-11-14T10:30:00"},
    )
    assert antwort.status_code == 400
    daten = antwort.json()
    assert "Überschneidung" in daten["fehler"] and daten["felder"]["__all__"]
    antwort = api.post(
        "eintraege", {"kategorie": "Mails", "start": "2026-11-14T12:00", "ende": "2026-11-14T11:00"}
    )
    assert antwort.status_code == 400 and "ende" in antwort.json()["felder"]
    antwort = api.post("eintraege", {"kategorie": "Mails", "start": "morgen", "ende": ""})
    assert antwort.status_code == 400 and {"start", "ende"} <= set(antwort.json()["felder"])
    assert Eintrag.objects.count() == 1


# --- Tag, Bewertung, Woche -------------------------------------------------------


def test_tag_ohne_bewertung_keine_merkmale(api, nutzer, kat):
    tag = tagesdatum(timezone.now())
    Eintrag.objects.create(
        nutzer=nutzer,
        kategorie=kat["Deep Work"],
        start=lokal(tag.year, tag.month, tag.day, 9),
        ende=lokal(tag.year, tag.month, tag.day, 10),
    )
    daten = api.get(f"tag/{tag}").json()
    assert len(daten["eintraege"]) == 1 and daten["bewertung"] is None
    assert daten["merkmale"] is None and "Tagesbewertung" in daten["hinweis"]


def test_bewertung_anlegen_aktualisieren_und_merkmale(api, nutzer, kat):
    tag = "2026-11-10"
    Eintrag.objects.create(
        nutzer=nutzer,
        kategorie=kat["Deep Work"],
        start=lokal(2026, 11, 10, 9),
        ende=lokal(2026, 11, 10, 10, 30),
    )
    antwort = api.post(
        f"tag/{tag}/bewertung", {"produktivitaet": 7, "zufriedenheit": 6, "schlaf_h": 7.5}
    )
    assert antwort.status_code == 201 and antwort.json()["bewertung"]["schlaf_h"] == 7.5
    antwort = api.post(
        f"tag/{tag}/bewertung", {"produktivitaet": 8, "zufriedenheit": 9, "notiz": "gut"}
    )
    assert antwort.status_code == 200
    b = Tagesbewertung.objects.get(nutzer=nutzer)
    assert (b.produktivitaet, b.zufriedenheit, b.notiz, b.schlaf_h) == (8, 9, "gut", None)
    merkmale = {m["key"]: m for m in api.get(f"tag/{tag}").json()["merkmale"]}
    assert (
        merkmale["deepwork_min"]["wert"] == 90
        and merkmale["deepwork_min"]["anzeige"] == "1 h 30 min"
    )


def test_bewertung_validierung(api, nutzer):
    for schlecht in ({"produktivitaet": 11, "zufriedenheit": 5}, {"produktivitaet": 5}, {}):
        antwort = api.post("tag/2026-11-10/bewertung", schlecht)
        assert antwort.status_code == 400 and antwort.json()["felder"], schlecht
    assert not Tagesbewertung.objects.exists()


def test_tag_zeigt_plan_vs_ist(api, nutzer, kat):
    Planblock.objects.create(
        nutzer=nutzer,
        kategorie=kat["Deep Work"],
        start=lokal(2026, 11, 10, 9),
        ende=lokal(2026, 11, 10, 11),
    )
    zeilen = api.get("tag/2026-11-10").json()["plan_ist"]
    assert zeilen == [
        {"art": "deepwork", "label": "Deep Work", "geplant": 120, "erfasst": 0, "differenz": -120}
    ]


def test_woche(api, nutzer, kat, django_assert_max_num_queries):
    bewerte_tage(nutzer, kat, 3)
    with django_assert_max_num_queries(8):  # kein N+1 über die Tage
        daten = api.get(f"woche/{tagesdatum(timezone.now())}").json()
    assert len(daten["tage"]) == 7 and daten["tage"][0]["datum"] == daten["von"]
    bewertet = [t for t in daten["tage"] if t["bewertet"]]
    assert all(t["deepwork_min"] and t["produktivitaet"] for t in bewertet)
    assert all(t["deepwork_min"] is None for t in daten["tage"] if not t["bewertet"])


# --- Muster ----------------------------------------------------------------------


def test_muster_unter_min_tage_und_darueber(api, nutzer, kat):
    bewerte_tage(nutzer, kat, 5)
    daten = api.get("muster").json()
    assert daten["fehlend"] == 9 and "Noch 9" in daten["hinweis"] and "zeilen" not in daten
    for modell in (Tagesbewertung, Eintrag, Messung):
        modell.objects.all().delete()
    bewerte_tage(nutzer, kat, 20)
    daten = api.get("muster", ziel="zufriedenheit").json()
    assert (
        daten["ziel"] == "zufriedenheit"
        and daten["zeilen"]
        and "keine Ursachen" in daten["hinweis"]
    )
    assert api.get("muster", ziel="quatsch").status_code == 400


# --- Plan ------------------------------------------------------------------------


def test_plan_anlegen_lesen_loeschen(api, nutzer, kat):
    antwort = api.post(
        "plan",
        {
            "kategorie": "Deep Work",
            "start": "2026-11-16T09:00",
            "ende": "2026-11-16T11:00",
            "titel": "Konzept",
        },
    )
    assert antwort.status_code == 201
    pk = antwort.json()["planblock"]["id"]
    antwort = api.post(
        "plan", {"kategorie": "Mails", "start": "2026-11-16T10:00", "ende": "2026-11-16T12:00"}
    )
    assert antwort.status_code == 400 and "Überschneidung" in antwort.json()["fehler"]
    bloecke = api.get("plan", start="2026-11-16", ende="2026-11-16").json()["planbloecke"]
    assert [b["titel"] for b in bloecke] == ["Konzept"]
    assert api.get("plan", start="2026-11-17", ende="2026-11-18").json()["planbloecke"] == []
    assert api.delete(f"plan/{pk}").status_code == 200
    assert not Planblock.objects.exists()


def test_plan_zeitraumgrenze(api):
    assert api.get("plan", start="2026-01-01", ende="2026-03-01").status_code == 200  # 60 Tage
    assert api.get("plan", start="2026-01-01", ende="2026-03-05").status_code == 400  # 64 Tage
    assert api.get("plan", start="2026-01-05", ende="2026-01-01").status_code == 400
    assert api.get("plan", start="2026-01-01").status_code == 400
    assert api.get("plan", start="kaputt", ende="2026-01-01").status_code == 400


# --- Isolation -------------------------------------------------------------------


def test_fremde_daten_unsichtbar(api, nutzer, kat):
    bob = get_user_model().objects.create_user("bob")
    lege_standardkategorien_an(bob)
    k = Kategorie.objects.get(nutzer=bob, name="Deep Work")
    Eintrag.objects.create(
        nutzer=bob, kategorie=k, start=lokal(2026, 11, 10, 9), ende=lokal(2026, 11, 10, 10)
    )
    Messung.objects.create(nutzer=bob, zeitpunkt=lokal(2026, 11, 10, 9), typ="wasser_ml", menge=999)
    Tagesbewertung.objects.create(
        nutzer=bob, datum=tagesdatum(timezone.now()), produktivitaet=5, zufriedenheit=5
    )
    fremder_plan = Planblock.objects.create(
        nutzer=bob, kategorie=k, start=lokal(2026, 11, 10, 9), ende=lokal(2026, 11, 10, 10)
    )
    tag = api.get("tag/2026-11-10").json()
    assert tag["eintraege"] == [] and tag["messungen"] == [] and tag["plan_ist"] is None
    assert api.get("jetzt").json()["heute"]["wasser_ml"] == 0
    assert api.get("plan", start="2026-11-10", ende="2026-11-10").json()["planbloecke"] == []
    assert api.delete(f"plan/{fremder_plan.pk}").status_code == 404
    assert Planblock.objects.filter(pk=fremder_plan.pk).exists()
    assert (
        api.post(
            "eintraege",
            {"kategorie": k.pk, "start": "2026-11-11T09:00", "ende": "2026-11-11T10:00"},
        ).status_code
        == 400
    )
    assert (
        api.post(
            "plan", {"kategorie": k.pk, "start": "2026-11-11T09:00", "ende": "2026-11-11T10:00"}
        ).status_code
        == 400
    )


# --- Einstellungen ---------------------------------------------------------------


def test_einstellungen_token_erzeugen_und_widerrufen(client, nutzer):
    assert client.get(reverse("einstellungen")).status_code == 302
    client.force_login(nutzer)
    antwort = client.post(reverse("einstellungen"), {"name": "Claude Desktop"})
    assert antwort.status_code == 200
    klartext = antwort.context["neu"]["klartext"]
    assert klartext in antwort.content.decode() and klartext.startswith("zt_")
    token = ApiToken.objects.get(nutzer=nutzer)
    assert token.token_hash == ApiToken.hash_von(klartext)
    seite = client.get(reverse("einstellungen")).content.decode()
    assert "Claude Desktop" in seite and klartext not in seite
    assert client.post(reverse("einstellungen"), {"name": ""}).context["neu"] is None
    fremd = get_user_model().objects.create_user("bob")
    fremdes = ApiToken.erzeugen(fremd, "bobs")[0]
    assert client.post(reverse("token_widerrufen", args=[fremdes.pk])).status_code == 404
    assert client.get(reverse("token_widerrufen", args=[token.pk])).status_code == 405
    assert client.post(reverse("token_widerrufen", args=[token.pk])).status_code == 302
    assert not ApiToken.objects.filter(nutzer=nutzer).exists()
