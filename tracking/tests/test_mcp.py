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


def test_experiment_tools_und_wochenbericht(mcp_env):
    import asyncio
    import json

    status = json.loads(server.experiment_status())
    assert status["laufend"] is None and len(status["vorlagen"]) == 8

    assert "Fehler 400" in server.experiment_starten(vorlage="gibtsnicht")
    gestartet = json.loads(server.experiment_starten(vorlage="mikropausen"))["experiment"]
    assert gestartet["titel"] == "Mikropausen" and len(gestartet["tage"]) == 20
    zweites = server.experiment_starten(vorlage="abschlussnotiz")
    assert zweites.startswith("Fehler 400") and "läuft schon" in zweites

    heute = gestartet["heute"]["datum"]
    bestaetigt = json.loads(server.experiment_tag_bestaetigen(heute, True))
    assert bestaetigt["eingehalten"] is True
    assert server.experiment_tag_bestaetigen("2000-01-01", True).startswith("Fehler 404")
    laufend = json.loads(server.experiment_status())["laufend"]
    assert laufend["einhaltung"] == {"antworten": 1, "ja": 1}
    assert "ergebnis" not in laufend  # Ergebnis erst nach dem Ende

    bericht = json.loads(server.wochenbericht_daten(heute))
    assert len(bericht["woche"]["tage"]) == 7
    assert bericht["laufendes_experiment"]["titel"] == "Mikropausen"
    assert len(bericht["experiment_vorlagen"]) == 8
    assert server.wochenbericht_daten("kaputt").startswith("Fehler 404")

    # eigene Felder statt Vorlage; es läuft aber schon eins
    eigen = server.experiment_starten(
        titel="Spazieren", regel_wenn="ich esse", regel_dann="gehe ich raus"
    )
    assert eigen.startswith("Fehler 400")

    namen = {p.name for p in asyncio.run(server.mcp.list_prompts())}
    assert "wochenbericht" in namen
    werkzeuge = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert {
        "experiment_status",
        "experiment_starten",
        "experiment_tag_bestaetigen",
        "wochenbericht_daten",
    } <= werkzeuge


def test_wochenbericht_prompt_enthaelt_die_regeln():
    text = server.wochenbericht("2026-11-09")
    assert "wochenbericht_daten" in text and "datum=2026-11-09" in text
    for regel in ("Hypothesen, keine Ursachen", "Pomodoro", "Starte nie von dir aus", "Vorlagen"):
        assert regel in text
    assert "aktuelle Woche" in server.wochenbericht()


def test_muster_ziel_schlaf_und_plan_faktor_ueber_mcp(mcp_env):
    import json

    assert json.loads(server.muster_abrufen("schlaf_h"))["ziel"] == "schlaf_h"
    plan = json.loads(server.plan_abrufen("2026-11-09", "2026-11-15"))
    assert plan["plan_faktor"] == []
    bewertet = server.tag_bewerten("2026-11-10", 7, 8, True, bettzeit="23:00", aufstehzeit="06:30")
    assert '"schlaf_h": 7.5' in bewertet
