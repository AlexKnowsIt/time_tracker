"""MCP-Server für die Zeiterfassung: KI-Assistenten bedienen die JSON-API (/api/v1/).

Start (stdio, Standard):   uv run --group mcp python mcp_server/server.py
Start (streamable-http):   uv run --group mcp python mcp_server/server.py --http [--port 8765]

Konfiguration über Umgebungsvariablen:
  ZEITERFASSUNG_URL    Basis-URL der App, z. B. https://zeit.example.org oder http://127.0.0.1:8000
  ZEITERFASSUNG_TOKEN  persönliches API-Token (App: Einstellungen). Wie ein Passwort behandeln.

Die HTTP-Aufrufe laufen mit der Standardbibliothek (urllib); Fehler der API kommen als
verständlicher Text zurück, nicht als Stacktrace.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Literal
from urllib.parse import quote, urlencode

from mcp.server.fastmcp import FastMCP

TIMEOUT_S = 15

mcp = FastMCP(
    "zeiterfassung",
    instructions=(
        "Persönliche Zeiterfassung. Ein Tag läuft von 04:00 bis 04:00 Uhr. Zeiten sind ISO 8601 "
        "(z. B. 2026-11-14T09:30:00+01:00); ohne Zeitzone gilt die Zeitzone der App. Die "
        "Auswertung zeigt Unterschiede, keine Ursachen. Beide Tagesscores (Produktivität, "
        "Zufriedenheit, je 1-10) gibt der Nutzer selbst an: nie raten oder erfinden."
    ),
)


def _konfig():
    """(Basis-URL, Token) aus der Umgebung. Fehlt etwas, gibt es eine klare Fehlermeldung."""
    url = os.environ.get("ZEITERFASSUNG_URL", "").strip().rstrip("/")
    token = os.environ.get("ZEITERFASSUNG_TOKEN", "").strip()
    fehlt = [n for n, w in (("ZEITERFASSUNG_URL", url), ("ZEITERFASSUNG_TOKEN", token)) if not w]
    if fehlt:
        raise RuntimeError(
            f"Umgebungsvariable(n) fehlen: {', '.join(fehlt)}. "
            "URL der App und persönliches Token (App: Einstellungen) setzen."
        )
    return url, token


def _fehlertext(daten, status):
    if isinstance(daten, dict) and daten.get("fehler"):
        text = f"Fehler {status}: {daten['fehler']}"
        felder = daten.get("felder")
        if felder:
            text += "\nFelder: " + json.dumps(felder, ensure_ascii=False)
        return text
    return f"Fehler {status}: unerwartete Antwort der API."


def _aufruf(methode, pfad, daten=None, abfrage=None):
    """Ruft die API auf und gibt die Antwort als Text zurück (JSON oder Fehlertext)."""
    try:
        url, token = _konfig()
    except RuntimeError as e:
        return f"Fehler: {e}"
    ziel = f"{url}/api/v1/{pfad}"
    if abfrage:
        ziel += "?" + urlencode(abfrage)
    anfrage = urllib.request.Request(
        ziel,
        data=json.dumps(daten).encode() if daten is not None else None,
        method=methode,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=TIMEOUT_S) as antwort:
            return json.dumps(json.load(antwort), ensure_ascii=False, indent=1)
    except urllib.error.HTTPError as e:
        try:
            return _fehlertext(json.load(e), e.code)
        except ValueError:
            return f"Fehler {e.code}: unerwartete Antwort der API."
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        grund = getattr(e, "reason", e)
        return f"Fehler: Zeiterfassung unter {url} nicht erreichbar ({grund})."
    except ValueError:
        return "Fehler: Die API hat kein gültiges JSON geliefert."


@mcp.tool()
def aktueller_stand() -> str:
    """Zeigt, was gerade läuft: der laufende Zeiteintrag (Kategorie, Start, Dauer), die aktiven
    Kategorien mit id, Name und Art sowie die heutige Trinkmenge (Wasser in ml, Kaffee).
    Zuerst aufrufen, wenn unklar ist, welcher Timer läuft oder welche Kategorien es gibt.
    Gibt JSON zurück. "laufend" ist null, wenn kein Timer läuft."""
    return _aufruf("GET", "jetzt")


@mcp.tool()
def timer_starten(kategorie: str) -> str:
    """Startet einen Timer in einer Kategorie und beendet dabei den laufenden Eintrag, falls
    einer läuft. Benutzen, wenn der Nutzer sagt, dass er jetzt etwas beginnt (Deep Work,
    Pause, Meeting ...). `kategorie` ist der Name (Groß-/Kleinschreibung egal) oder die id
    einer aktiven Kategorie, siehe aktueller_stand. Gibt den neuen Eintrag als JSON zurück."""
    return _aufruf("POST", "start", {"kategorie": kategorie})


@mcp.tool()
def timer_stoppen() -> str:
    """Beendet den laufenden Zeiteintrag, ohne einen neuen zu starten. Benutzen, wenn der
    Nutzer aufhört (Feierabend). Gibt den beendeten Eintrag mit Dauer zurück, oder einen
    Hinweis, wenn nichts lief."""
    return _aufruf("POST", "stopp")


@mcp.tool()
def trinken_erfassen(
    typ: Literal["wasser_ml", "kaffee"] = "wasser_ml", menge: int | None = None
) -> str:
    """Erfasst Getränke zum aktuellen Zeitpunkt. `typ`: "wasser_ml" (Menge in ml, Standard
    250) oder "kaffee" (Anzahl Tassen, Standard 1). `menge` nur angeben, wenn der Nutzer eine
    andere Menge nennt (1 bis 5000). Gibt die Messung und die Tagessummen zurück."""
    daten = {"typ": typ}
    if menge is not None:
        daten["menge"] = menge
    return _aufruf("POST", "messung", daten)


@mcp.tool()
def eintrag_nachtragen(
    kategorie: str,
    start: str,
    ende: str,
    notiz: str = "",
    abgeschlossen: bool | None = None,
    unterbrochen: bool = False,
) -> str:
    """Trägt einen vergangenen Zeitblock nach, wenn der Nutzer vergessen hat zu erfassen.
    `kategorie`: Name oder id. `start` und `ende`: ISO 8601, z. B. 2026-11-14T09:30:00+01:00
    (ohne Zeitzone gilt die der App). Das Ende muss nach dem Start liegen. Einträge dürfen
    sich nicht überschneiden: bei Überschneidung kommt ein Fehlertext mit dem Konflikt, dann
    die Zeiten anpassen. Nachgetragene Einträge gelten als rekonstruiert (Kennzeichen
    "nachgetragen"). Optional: `abgeschlossen` (Aufgabe abgeschlossen? nur angeben, wenn
    der Nutzer es sagt) und `unterbrochen` (Block wurde unterbrochen). Gibt den neuen Eintrag
    als JSON zurück."""
    daten = {
        "kategorie": kategorie,
        "start": start,
        "ende": ende,
        "notiz": notiz,
        "unterbrochen": unterbrochen,
    }
    if abgeschlossen is not None:
        daten["abgeschlossen"] = abgeschlossen
    return _aufruf("POST", "eintraege", daten)


@mcp.tool()
def tag_abrufen(datum: str) -> str:
    """Liefert einen Tag (JJJJ-MM-TT; Tag = 04:00 bis 04:00 Uhr): Einträge, Messungen,
    Bewertung und Plan gegen Ist je Kategorie-Art. Die berechneten Tagesmerkmale (Deep-Work-
    Blöcke, Pausen, Wechsel ...) kommen erst, wenn der Tag bewertet ist (Score vor Statistik);
    sonst ist "merkmale" null. Benutzen für Rückblicke auf einen einzelnen Tag."""
    return _aufruf("GET", f"tag/{quote(datum, safe='')}")


@mcp.tool()
def tag_bewerten(
    datum: str,
    produktivitaet: int,
    zufriedenheit: int,
    fortschritt: bool,
    schlaf_h: float | None = None,
    notiz: str = "",
    fortschritt_notiz: str = "",
    abgeschaltet: int | None = None,
    bettzeit: str | None = None,
    aufstehzeit: str | None = None,
) -> str:
    """Speichert die Tagesbewertung (JJJJ-MM-TT) oder ersetzt eine vorhandene vollständig.
    `produktivitaet` ("Wie produktiv war der Tag?") und `zufriedenheit` ("Wie zufrieden bist
    du mit dem Tag?") sind ganze Zahlen von 1 bis 10, `fortschritt` ("Hast du heute bei etwas
    Wichtigem Fortschritt gemacht?") ist ja/nein. Alle drei muss der Nutzer selbst nennen,
    nie schätzen. Optional: `fortschritt_notiz` (was genau), `abgeschaltet` ("Wie gut konntest
    du nach der Arbeit abschalten?", 1 bis 5), `schlaf_h` (Stunden), `bettzeit` (letzte Nacht)
    und `aufstehzeit` (heute) als HH:MM (daraus wird `schlaf_h` berechnet, falls leer), `notiz`
    (was hat geholfen, was gestört). Gibt die gespeicherte Bewertung zurück."""
    daten = {
        "produktivitaet": produktivitaet,
        "zufriedenheit": zufriedenheit,
        "fortschritt": fortschritt,
        "fortschritt_notiz": fortschritt_notiz,
        "notiz": notiz,
    }
    if schlaf_h is not None:
        daten["schlaf_h"] = schlaf_h
    if abgeschaltet is not None:
        daten["abgeschaltet"] = abgeschaltet
    if bettzeit:
        daten["bettzeit"] = bettzeit
    if aufstehzeit:
        daten["aufstehzeit"] = aufstehzeit
    return _aufruf("POST", f"tag/{quote(datum, safe='')}/bewertung", daten)


@mcp.tool()
def woche_abrufen(datum: str) -> str:
    """Übersicht der Woche (Montag bis Sonntag), die das Datum (JJJJ-MM-TT) enthält: je Tag
    beide Scores und Deep-Work-Minuten. Beides gibt es nur für bewertete Tage, sonst null.
    Benutzen für einen schnellen Wochenrückblick."""
    return _aufruf("GET", f"woche/{quote(datum, safe='')}")


@mcp.tool()
def muster_abrufen(
    ziel: Literal["produktivitaet", "zufriedenheit", "schlaf_h"] = "produktivitaet",
) -> str:
    """Wertet die letzten 180 Tage nach der Zielgröße `ziel` aus (Produktivität, Zufriedenheit
    oder Schlaf in Stunden), in drei Stufen: (1) gute
    gegen schwache Tage (oberes gegen unteres Drittel; je Merkmal Mittelwerte, Cliff's Delta
    mit Intervall und "deutlich"), erst ab 14 bewerteten Tagen; (2) "korrelationen"
    (Spearman, wochentagsbereinigt, Intervall, Mehrfachtest-Treffer, Autokorrelation), ab 30
    Tagen; (3) "mehrfachmodell" (die fünf stärksten Merkmale einer gemeinsamen Regression),
    ab 90 Tagen. Ist eine Stufe noch nicht erreicht, steht dort, wie viele Tage fehlen.
    Dazu "sozialer_jetlag_min" (Schlafmitte freier Tage minus Werktage, 28 Tage) und
    "anteil_nachgetragen" (Anteil rekonstruierter Einträge). Das sind Unterschiede und
    Zusammenhänge, keine Ursachen: als Hypothesen formulieren, Ursachen prüft man mit
    Experimenten."""
    return _aufruf("GET", "muster", abfrage={"ziel": ziel})


@mcp.tool()
def plan_abrufen(start: str, ende: str) -> str:
    """Listet geplante Zeitblöcke im Zeitraum (höchstens 62 Tage). `start` und `ende` sind
    Daten (JJJJ-MM-TT, Ende einschließlich) oder ISO-8601-Zeitpunkte. Gibt je Block id,
    Kategorie, Zeiten und Titel zurück, dazu "plan_faktor": je Kategorie-Art, wie viel Prozent
    des Plans der Nutzer im Median der letzten 28 Tage schafft (Planning Fallacy). Beim Planen
    Dauern mit diesem Faktor großzügiger ansetzen."""
    return _aufruf("GET", "plan", abfrage={"start": start, "ende": ende})


@mcp.tool()
def planblock_anlegen(kategorie: str, start: str, ende: str, titel: str = "") -> str:
    """Plant einen Zeitblock (Soll für "Plan vs. Ist"). `kategorie`: Name oder id. `start`
    und `ende`: ISO 8601 mit Zeitzone, z. B. 2026-11-16T09:00:00+01:00. Planblöcke dürfen
    sich nicht überschneiden. `titel` optional (z. B. "Konzept schreiben"). Gibt den Block
    mit id zurück."""
    return _aufruf(
        "POST",
        "plan",
        {"kategorie": kategorie, "start": start, "ende": ende, "titel": titel},
    )


@mcp.tool()
def planblock_loeschen(id: int) -> str:
    """Löscht einen Planblock anhand seiner id (siehe plan_abrufen). Nur auf ausdrücklichen
    Wunsch des Nutzers benutzen; das Löschen lässt sich nicht rückgängig machen."""
    return _aufruf("DELETE", f"plan/{int(id)}")


@mcp.tool()
def experiment_status() -> str:
    """Zeigt das laufende Selbstexperiment (Regel, Zielgröße, Fortschritt, heutige Bedingung A
    oder B, Einhaltung, Zuweisung aller Tage), die beendeten mit vorsichtig formuliertem
    Ergebnis und die acht Vorlagen mit ihrem Schlüssel (für experiment_starten). Das Ergebnis
    eines laufenden Experiments gibt es bewusst erst nach dem Ende. Ergebnisse sind Hinweise
    aus einem kleinen Selbstexperiment, kein Beweis."""
    return _aufruf("GET", "experiment")


@mcp.tool()
def experiment_starten(
    vorlage: str = "",
    titel: str = "",
    hypothese: str = "",
    regel_wenn: str = "",
    regel_dann: str = "",
    design: Literal["tageweise", "bloecke", "abab", ""] = "",
    blocklaenge: int | None = None,
    dauer_tage: int | None = None,
    zielgroesse: str = "",
    start: str = "",
) -> str:
    """Startet ein Selbstexperiment. Nur auf ausdrücklichen Wunsch des Nutzers, nie von sich
    aus. Entweder `vorlage` (Schlüssel aus experiment_status, z. B. "mikropausen") oder eigene
    Felder: `titel`, `hypothese` (was erwartet der Nutzer), Regel als `regel_wenn` ("es 14 Uhr
    ist") und `regel_dann` ("trinke ich keinen Kaffee mehr"), `design` ("tageweise",
    "bloecke", "abab"), `blocklaenge` (Tage je Block bzw. Phase), `dauer_tage` (8 bis 120; bei
    abab 4 x Phasenlänge), `zielgroesse` (produktivitaet, zufriedenheit, abgeschaltet,
    schlaf_folgenacht, deepwork_min, wechsel_pro_h, beginn, plan_erfuellung), `start`
    (JJJJ-MM-TT, Standard heute). Zu einer Vorlage überschreiben angegebene Felder die
    Vorgaben. Die Bedingung jedes Tages wird sofort zufällig zugewiesen und ist danach
    unveränderlich; auch Hypothese, Regel, Zielgröße und Dauer. Es kann nur ein Experiment
    gleichzeitig laufen."""
    daten = {
        k: v
        for k, v in {
            "vorlage": vorlage,
            "titel": titel,
            "hypothese": hypothese,
            "regel_wenn": regel_wenn,
            "regel_dann": regel_dann,
            "design": design,
            "blocklaenge": blocklaenge,
            "dauer_tage": dauer_tage,
            "zielgroesse": zielgroesse,
            "start": start,
        }.items()
        if v not in ("", None)
    }
    return _aufruf("POST", "experiment", daten)


@mcp.tool()
def experiment_tag_bestaetigen(datum: str, eingehalten: bool) -> str:
    """Trägt für einen Tag (JJJJ-MM-TT) des laufenden Experiments ein, ob die Bedingung
    eingehalten wurde ("Hast du dich heute an die Bedingung gehalten?"). Die Antwort muss der
    Nutzer selbst geben, nie raten. Fehler, wenn an dem Tag kein Experimenttag existiert."""
    return _aufruf("POST", f"experiment/tag/{quote(datum, safe='')}", {"eingehalten": eingehalten})


@mcp.tool()
def wochenbericht_daten(datum: str) -> str:
    """Liefert kompakt alles für einen Wochenrückblick der Woche (Montag bis Sonntag), die das
    Datum (JJJJ-MM-TT) enthält: je Tag Scores, Notizen und Tagesmerkmale (nur bewertete Tage),
    Durchschnitt der 4 Wochen davor, die wichtigsten Muster-Hinweise (Unterschiede und
    Zusammenhänge, keine Ursachen), Plan-Faktor, sozialen Jetlag, das laufende Experiment und
    die Experiment-Vorlagen. Wird vom Prompt "wochenbericht" genutzt."""
    return _aufruf("GET", f"wochenbericht/{quote(datum, safe='')}")


WOCHENBERICHT_ANWEISUNG = """\
Schreibe einen kurzen deutschen Wochenrückblick (höchstens 200 Wörter) zur Zeiterfassung.

Vorgehen:
1. Rufe das Tool wochenbericht_daten auf{woche}.
2. Fasse die Woche knapp zusammen: Scores im Vergleich zu den 4 Wochen davor, Deep Work,
   Tage mit Fortschritt, auffällige Tage. Erwähne nur Zahlen, die in den Daten stehen.
3. Nenne ein bis zwei Auffälligkeiten aus den Muster-Hinweisen, nur wenn dort welche stehen.
4. Schlage höchstens zwei passende Experimente aus den Vorlagen (experiment_vorlagen) vor, mit
   Titel und Wenn-dann-Regel. Starte nie von dir aus ein Experiment: Der Nutzer entscheidet.
   Läuft schon eines, erwähne es und schlage kein neues vor.

Regeln (Forschungsgrundlage der App, docs/forschung.md, „Was die App nicht behauptet“):
- Formuliere Hypothesen, keine Ursachen: „könnte zusammenhängen“, „fällt auf“, nie „führt
  zu“ oder „verursacht“. Kausale Aussagen gibt es nur nach einem randomisierten
  Selbstexperiment, und auch dann vorsichtig.
- Keine festen Arbeitsrhythmen (90/20, Pomodoro) empfehlen.
- Kein „mehr Wasser oder Kaffee steigert den Fokus“.
- Keine Pauschalzahlen wie „40 % Verlust durch Kontextwechsel“ oder „23 Minuten
  Wiederaufnahme“.
- Weise bei Tagen ohne Bewertung darauf hin, statt Werte zu schätzen. Erfinde nichts, rate
  keine Scores.
- Ist ein hoher Anteil nachgetragen (> 50 %), erwähne, dass die Merkmale dann rekonstruiert
  und ungenauer sind.
"""


@mcp.prompt()
def wochenbericht(datum: str = "") -> str:
    """Vorsichtiger Wochenrückblick mit ein bis zwei Experiment-Vorschlägen. `datum`
    (JJJJ-MM-TT) wählt die Woche; leer = die aktuelle Woche."""
    woche = f" mit datum={datum}" if datum else " für die aktuelle Woche (heutiges Datum)"
    return WOCHENBERICHT_ANWEISUNG.format(woche=woche)


def main(argv=None):
    parser = argparse.ArgumentParser(description="MCP-Server für die Zeiterfassung")
    parser.add_argument("--http", action="store_true", help="streamable-http statt stdio")
    parser.add_argument("--port", type=int, default=8765, help="Port für --http (Standard 8765)")
    args = parser.parse_args(argv)
    try:
        _konfig()
    except RuntimeError as e:
        sys.exit(f"Fehler: {e}")
    if args.http:
        # Bindet nur an 127.0.0.1: Der MCP-HTTP-Endpunkt hat hier keine eigene Authentifizierung;
        # wer ihn erreicht, nutzt das Token des Servers. Nie auf 0.0.0.0 öffnen.
        mcp.settings.host, mcp.settings.port = "127.0.0.1", args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
