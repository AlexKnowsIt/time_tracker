"""MCP-Tools gegen einen echten Server (live_server). Ohne Gruppe ``mcp`` übersprungen."""

import pytest

pytest.importorskip("mcp")

from django.contrib.auth import get_user_model  # noqa: E402

from mcp_server import server  # noqa: E402
from tracking.models import ApiToken, Eintrag  # noqa: E402
from tracking.services import lege_standardkategorien_an  # noqa: E402


@pytest.fixture
def mcp_env(live_server, monkeypatch, transactional_db):
    nutzer = get_user_model().objects.create_user("anna")
    lege_standardkategorien_an(nutzer)
    monkeypatch.setenv("ZEITERFASSUNG_URL", live_server.url)
    monkeypatch.setenv("ZEITERFASSUNG_TOKEN", ApiToken.erzeugen(nutzer, "mcp")[1])
    return nutzer


def test_start_stopp_trinken_tag(mcp_env):
    assert '"laufend": null' in server.aktueller_stand()
    assert "Deep Work" in server.timer_starten("deep work")
    assert Eintrag.objects.get(nutzer=mcp_env, ende=None).kategorie.name == "Deep Work"
    assert '"laeuft": false' in server.timer_stoppen()
    assert '"wasser_ml": 250' in server.trinken_erfassen()
    assert '"kaffee": 2' in server.trinken_erfassen("kaffee", 2)
    tag = server.tag_abrufen("2026-11-10")
    assert '"merkmale": null' in tag
    assert "Fehler 400" in server.tag_bewerten("2026-11-10", 11, 5, True)
    assert '"produktivitaet": 7' in server.tag_bewerten(
        "2026-11-10", 7, 8, True, notiz="ok", abgeschaltet=4
    )


def test_fehlertexte_statt_stacktrace(mcp_env, monkeypatch):
    text = server.timer_starten("Gibt es nicht")
    assert text.startswith("Fehler 404:") and "Vorhandene:" in text and "Traceback" not in text
    assert server.planblock_loeschen(999).startswith("Fehler 404")
    assert server.tag_abrufen("kaputt").startswith("Fehler 404")
    monkeypatch.setenv("ZEITERFASSUNG_TOKEN", "zt_falsch")
    assert server.aktueller_stand().startswith("Fehler 401")
    monkeypatch.setenv("ZEITERFASSUNG_URL", "http://127.0.0.1:9")
    assert "nicht erreichbar" in server.aktueller_stand()


def test_konfiguration_fehlt(monkeypatch):
    monkeypatch.delenv("ZEITERFASSUNG_URL", raising=False)
    monkeypatch.delenv("ZEITERFASSUNG_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="ZEITERFASSUNG_URL, ZEITERFASSUNG_TOKEN"):
        server.main([])
    assert server.aktueller_stand().startswith("Fehler:")
