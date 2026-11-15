import json
import re
import stat
import sys

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import Client
from django.urls import set_script_prefix

from tracking.models import Kategorie
from zeiterfassung import betriebsmodus, desktop

PRAEFIX = "/api/hassio_ingress/tok3n"
SUPERVISOR = {"REMOTE_ADDR": "172.30.32.2", "HTTP_X_INGRESS_PATH": PRAEFIX}


@pytest.fixture(autouse=True)
def _prefix_zuruecksetzen():
    yield
    set_script_prefix("/")
    desktop.geheimnis_registrieren(None)


def _mw(*namen):
    from django.conf import settings

    basis = list(settings.MIDDLEWARE)
    i = basis.index("django.contrib.auth.middleware.AuthenticationMiddleware")
    ingress = [f"zeiterfassung.ingress.{n}" for n in namen if n == "IngressMiddleware"]
    ha = [f"zeiterfassung.ingress.{n}" for n in namen if n == "HaAnmeldungMiddleware"]
    return basis[:1] + ingress + basis[1 : i + 1] + ha + basis[i + 1 :]


@pytest.fixture
def ha(settings):
    settings.ZEITERFASSUNG_MODUS = "homeassistant"
    settings.STATIC_URL = "/static/"
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "zeiterfassung.ingress.IngressStaticFilesStorage"},
    }
    settings.ALLOWED_HOSTS = ["*"]
    settings.MIDDLEWARE = _mw("IngressMiddleware")
    return settings


# --- Ingress ---------------------------------------------------------------------------------


@pytest.mark.django_db
def test_ingress_login_redirect_seite_und_statische_url_tragen_das_praefix(ha):
    client = Client()
    antwort = client.get("/tag/", **SUPERVISOR)
    assert antwort.status_code == 302
    assert antwort["Location"] == f"{PRAEFIX}/login/?next={PRAEFIX}/tag/"

    seite = client.get("/login/", **SUPERVISOR)
    html = seite.content.decode()
    assert f'href="{PRAEFIX}/static/tracking/app.css"' in html
    assert f'href="{PRAEFIX}/manifest.webmanifest"' in html


@pytest.mark.django_db
def test_ingress_post_mit_csrf_und_redirect_nach_login(ha):
    get_user_model().objects.create_user("anna", password="geheim-12345")
    client = Client(enforce_csrf_checks=True)
    seite = client.get("/login/", **SUPERVISOR)
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', seite.content.decode())[1]
    antwort = client.post(
        "/login/",
        {"username": "anna", "password": "geheim-12345", "csrfmiddlewaretoken": token},
        **SUPERVISOR,
    )
    assert antwort.status_code == 302
    assert antwort["Location"] == f"{PRAEFIX}/"
    innen = client.get("/", **SUPERVISOR)
    assert innen.status_code == 200
    assert f'href="{PRAEFIX}/tag/"' in innen.content.decode()


@pytest.mark.django_db
def test_ingress_post_ohne_csrf_wird_abgelehnt(ha):
    client = Client(enforce_csrf_checks=True)
    assert client.post("/login/", {}, **SUPERVISOR).status_code == 403


@pytest.mark.django_db
def test_ingress_manifest_zeigt_auf_das_praefix(ha):
    daten = json.loads(Client().get("/manifest.webmanifest", **SUPERVISOR).content)
    assert daten["start_url"] == f"{PRAEFIX}/"
    assert daten["icons"][0]["src"] == f"{PRAEFIX}/static/tracking/icon.svg"


@pytest.mark.django_db
def test_ingress_header_von_fremder_adresse_wird_ignoriert(ha):
    antwort = Client().get("/tag/", REMOTE_ADDR="10.0.0.5", HTTP_X_INGRESS_PATH=PRAEFIX)
    assert antwort["Location"] == "/login/?next=/tag/"


@pytest.mark.django_db
@pytest.mark.parametrize("boese", ["http://evil.example", "//evil.example", '/a"b', "/../x"])
def test_ingress_unsicheres_praefix_wird_verworfen(ha, boese):
    antwort = Client().get("/tag/", REMOTE_ADDR="172.30.32.2", HTTP_X_INGRESS_PATH=boese)
    assert antwort["Location"] == "/login/?next=/tag/"


@pytest.mark.django_db
def test_ingress_host_kommt_aus_x_forwarded_host(ha):
    # Browser-Origin passt nur, wenn der weitergereichte Host gilt (CSRF-Ursprungsprüfung)
    client = Client(enforce_csrf_checks=True)
    antwort = client.post(
        "/login/",
        {},
        HTTP_ORIGIN="https://ha.example.org",
        HTTP_X_FORWARDED_HOST="ha.example.org",
        HTTP_X_FORWARDED_PROTO="https",
        **SUPERVISOR,
    )
    assert "Origin checking failed" not in antwort.content.decode()


@pytest.mark.django_db
def test_ha_anmeldung_legt_nutzer_an_und_loggt_ein(ha):
    ha.MIDDLEWARE = _mw("IngressMiddleware", "HaAnmeldungMiddleware")
    client = Client()
    antwort = client.get("/", HTTP_X_REMOTE_USER_NAME="Anna", **SUPERVISOR)
    assert antwort.status_code == 200
    nutzer = get_user_model().objects.get(username="Anna")
    assert not nutzer.has_usable_password()
    assert Kategorie.objects.filter(nutzer=nutzer).exists()
    # Fremde Adresse und API-Pfade loggen nicht ein
    assert Client().get("/", REMOTE_ADDR="10.0.0.5").status_code == 302
    assert Client().get("/api/v1/jetzt", **SUPERVISOR).status_code == 401


# --- Desktop-Anmeldung -----------------------------------------------------------------------


@pytest.mark.django_db
def test_desktop_anmeldung_gilt_einmal_und_loggt_lokalen_nutzer_ein(settings):
    settings.ZEITERFASSUNG_MODUS = "desktop"
    settings.ROOT_URLCONF = "zeiterfassung.tests.urls_desktop"
    desktop.geheimnis_registrieren("geheimnis-1")
    client = Client()
    assert client.get("/desktop-anmeldung/falsch/").status_code == 404
    antwort = client.get("/desktop-anmeldung/geheimnis-1/")
    assert antwort.status_code == 302 and antwort["Location"] == "/"
    nutzer = get_user_model().objects.get(username="lokal")
    assert nutzer.is_superuser and not nutzer.has_usable_password()
    assert client.get("/").status_code == 200
    # zweiter Aufruf, auch von einem anderen Client: Geheimnis verbraucht
    assert Client().get("/desktop-anmeldung/geheimnis-1/").status_code == 404


@pytest.mark.django_db
def test_desktop_anmeldung_nicht_ohne_registriertes_geheimnis(settings):
    settings.ZEITERFASSUNG_MODUS = "desktop"
    settings.ROOT_URLCONF = "zeiterfassung.tests.urls_desktop"
    assert Client().get("/desktop-anmeldung/irgendwas/").status_code == 404


@pytest.mark.django_db
def test_desktop_anmeldung_im_servermodus_nicht_erreichbar():
    desktop.geheimnis_registrieren("geheimnis-2")
    assert Client().get("/desktop-anmeldung/geheimnis-2/").status_code == 404  # keine Route


@pytest.mark.django_db
def test_desktop_anmeldung_view_prueft_modus_selbst(settings):
    # selbst wenn die Route fälschlich registriert wäre
    settings.ROOT_URLCONF = "zeiterfassung.tests.urls_desktop"
    desktop.geheimnis_registrieren("geheimnis-3")
    assert Client().get("/desktop-anmeldung/geheimnis-3/").status_code == 404


# --- Betriebsmodus-Helfer --------------------------------------------------------------------


def test_modus_aus_umgebung_oder_optionsdatei(tmp_path):
    optionen = tmp_path / "options.json"
    assert betriebsmodus.erkenne_modus({}, optionen) == "server"
    optionen.write_text("{}")
    assert betriebsmodus.erkenne_modus({}, optionen) == "homeassistant"
    assert betriebsmodus.erkenne_modus({"ZEITERFASSUNG_MODUS": "desktop"}, optionen) == "desktop"
    with pytest.raises(ImproperlyConfigured):
        betriebsmodus.erkenne_modus({"ZEITERFASSUNG_MODUS": "quatsch"}, optionen)


def test_optionen_laden_prueft_werte(tmp_path):
    datei = tmp_path / "options.json"
    assert betriebsmodus.optionen_laden(datei) == {
        "zeitzone": "Europe/Berlin",
        "csrf_trusted_origins": [],
    }
    datei.write_text(
        json.dumps({"zeitzone": "Europe/Vienna", "csrf_trusted_origins": ["https://ha.example/"]})
    )
    assert betriebsmodus.optionen_laden(datei) == {
        "zeitzone": "Europe/Vienna",
        "csrf_trusted_origins": ["https://ha.example"],
    }
    datei.write_text(json.dumps({"zeitzone": "Mars/Olympus"}))
    with pytest.raises(ImproperlyConfigured):
        betriebsmodus.optionen_laden(datei)
    datei.write_text(json.dumps({"csrf_trusted_origins": ["ha.example"]}))
    with pytest.raises(ImproperlyConfigured):
        betriebsmodus.optionen_laden(datei)


def test_geheimnis_wird_einmal_erzeugt_und_bleibt(tmp_path):
    pfad = tmp_path / "daten" / "secret_key"
    erster = betriebsmodus.geheimnis_laden(pfad)
    assert len(erster) >= 64
    assert betriebsmodus.geheimnis_laden(pfad) == erster
    if sys.platform != "win32":
        assert stat.S_IMODE(pfad.stat().st_mode) == 0o600
