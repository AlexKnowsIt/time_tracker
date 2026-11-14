# Zielbild: Zeiterfassung mit Tagesauswertung

Stand: November 2026. Dieses Dokument beschreibt, wohin das Projekt gehen soll,
warum die Architektur so gewählt ist und in welchen Schritten es entsteht.

## 1. Worum es geht

Ich erfasse über den Tag, was ich mache, wann ich Pause mache und wie viel ich
trinke. Am Abend bewerte ich den Tag mit zwei Scores: wie produktiv er war und wie zufrieden ich mit ihm bin. Die App
zeigt mir mit der Zeit, welche Muster gute Tage von schlechten unterscheiden:
zum Beispiel Pausenzeitpunkte, lange Deep-Work-Blöcke statt Zerstückelung, Trinkmenge
oder Arbeitsbeginn.

**Erfolgskriterium:** Nach zwei Wochen sehe ich erste belastbare Unterschiede
zwischen guten und schlechten Tagen. Nach vier bis sechs Wochen habe ich eine
Handvoll konkreter Hypothesen, die ich gezielt ausprobieren kann.

## 2. Das größte Risiko ist nicht die Technik

Solche Projekte scheitern fast immer daran, dass man nach einer Woche aufhört
zu erfassen. Deshalb gilt für jede Entscheidung:

- **Jede Erfassung dauert unter 5 Sekunden.** Ein Tipp auf „Jetzt: Deep Work“ beendet
  den laufenden Block und startet den neuen. „+250 ml“ ist ein Tipp.
- **Vergessen ist erlaubt.** Einträge lassen sich nachträglich korrigieren,
  Lücken werden in der Tagesansicht sichtbar und können beim Tagesabschluss
  gefüllt werden.
- **Die App liefert ab Tag 1 etwas zurück.** Die Tagesansicht als Zeitleiste ist
  sofort nützlich, auch ohne jede Statistik.
- **Läuft auf dem Handy.** Installierbar als Web-App auf dem Startbildschirm.

## 3. Architektur

### Entscheidung: Python + Django bleibt, aber neu aufgesetzt

| Option | Bewertung |
|---|---|
| **Django + Templates + HTMX + SQLite** | **Gewählt.** Login, Admin-Oberfläche, ORM, Migrationen und Formulare sind eingebaut. Python ist die beste Sprache für die spätere Auswertung. Eine Sprache, ein Prozess, eine Datei als Datenbank. |
| FastAPI + React/Svelte | Zwei Codebasen, zwei Sprachen, eigenes Auth und Admin. Lohnt sich erst bei einer echten API für mehrere Clients. |
| Reine Browser-App (lokal, ohne Server) | Kein Server nötig, aber Daten liegen nur auf einem Gerät. Synchronisierung Handy/Laptop wäre ein eigenes Projekt. Auswertung in JavaScript ist mühsamer. |
| Fertiges Tool (Toggl, Clockify) + Auswertung als Notebook | Ehrlich gesagt der schnellste Weg zu Ergebnissen. Fällt raus, weil Tagesbewertung, Trinken und die Verknüpfung in einer App das Ziel sind und das Projekt auch ein Lernprojekt ist. Bleibt als Rückfallebene. |

### Bausteine

- **Python 3.13, Django 5.2 LTS** (Support bis April 2028).
- **HTMX** für die Timer-Knöpfe und schnelle Eingaben ohne Seiten-Neuladen.
  Kein JavaScript-Framework, kein Build-Schritt.
- **SQLite** im WAL-Modus. Für einen bis wenige Nutzer mehr als ausreichend.
  Backup ist das Kopieren einer Datei.
- **Auswertung mit der Standardbibliothek.** `statistics.correlation(x, y,
  method="ranked")` liefert seit Python 3.12 die Spearman-Korrelation. Bei
  einigen hundert Tagen braucht es weder pandas noch scipy. Erst bei
  Regressionen in Phase 5 kommt eine Bibliothek dazu.
- **Diagramme:** Die Zeitleiste ist reines HTML/CSS. Für Verläufe reicht
  Chart.js, eingebunden per CDN.
- **PWA-Manifest**, damit die App auf dem Handy wie eine App startet.
- **Werkzeuge:** `uv` für Abhängigkeiten, `ruff` für Formatierung und Linting,
  `pytest` mit `pytest-django` für Tests.
- **Konfiguration über Umgebungsvariablen.** `SECRET_KEY` und `DEBUG` stehen nie
  im Repo. Zeitzone `Europe/Berlin`, `USE_TZ = True`.
- **Betrieb:** ein Container auf dem eigenen Server hinter Cloudflare Access,
  zusätzlich Django-Login. Nächtliches Backup der SQLite-Datei.

### Projektstruktur

```
zeiterfassung/        Projekt-Einstellungen, URLs
tracking/             Einzige App: Modelle, Views, Templates
  models.py
  views.py            Timer, Tagesansicht, Tagesabschluss
  merkmale.py         Berechnung der Tagesmerkmale (reine Funktionen)
  auswertung.py       Vergleiche, Korrelationen (reine Funktionen)
  templates/tracking/
  tests/
docs/
```

Eine App reicht. Aufteilen lohnt sich erst, wenn ein Teil wirklich eigenständig
wird. `merkmale.py` und `auswertung.py` sind reine Funktionen ohne Django-Bezug,
damit sie einfach testbar sind.

## 4. Datenmodell

Kernidee: **Rohdaten erfassen, Kennzahlen berechnen.** Gespeichert werden nur
Ereignisse mit Zeitstempel. Alles, was man auswerten will (Pausen, Blocklängen,
Wechsel), wird daraus abgeleitet. So kann man später neue Fragen an alte Daten
stellen.

```
Kategorie
  name            "Deep Work", "Mails", "Meetings", "Organisation", "Pause", "Sport", "Freizeit"
  art             deepwork | shallowwork | organisation | pause | freizeit
  farbe
  aktiv           alte Kategorien ausblenden statt löschen
  nutzer → User

Eintrag           ein Zeitblock
  start           Zeitpunkt
  ende            Zeitpunkt, leer = läuft gerade
  kategorie → Kategorie
  notiz           optional
  nutzer → User
  Regel: pro Nutzer höchstens ein laufender Eintrag

Messung           zählbare Dinge zu einem Zeitpunkt
  zeitpunkt
  typ             wasser_ml | kaffee | ...
  menge
  nutzer → User

Tagesbewertung    einmal pro Tag, beim Tagesabschluss
  datum           eindeutig pro Nutzer
  produktivitaet  1–10: „Wie produktiv war der Tag?“
  zufriedenheit   1–10: „Wie zufrieden bist du mit dem Tag?“
  schlaf_h        optional
  notiz           „Was hat geholfen, was hat gestört?“
  nutzer → User
```

Begründungen:

- **Kategorien statt fester Spalten.** Die alte Version hatte drei feste Felder.
  Jede neue Tätigkeit hätte eine Migration gebraucht. Jetzt ist es ein Datensatz.
- **`art` an der Kategorie** fasst viele Kategorien für die Auswertung zusammen:
  „Deep-Work-Zeit“ ist die Summe aller Kategorien der Art `deepwork`. Die Arten
  stammen aus dem Prototyp von 2021: Deep Work (konzentriert, ungestört) gegen Shallow Work
  (Mails, Meetings), dazu Organisation, Pause und Freizeit. Arbeits-Arten sind Deep Work,
  Shallow Work und Organisation.
- **Pausen werden aktiv erfasst** (Kategorie der Art `pause`). Eine Lücke
  zwischen Einträgen ist „nicht erfasst“ und keine Pause. Sonst verfälscht jede
  vergessene Erfassung die Statistik.
- **`Messung` ist allgemein.** Wasser, Kaffee und später anderes brauchen keine
  neue Tabelle.
- **Nutzerbezug von Anfang an.** Kostet jetzt ein Feld, später eine schmerzhafte
  Migration. Damit kann auch Damjan die App nutzen.
- **Tagesgrenze 04:00 Uhr.** Arbeit bis 1 Uhr nachts zählt zum Vortag.
  Einträge über Mitternacht gehören zum Tag ihres Starts.

## 5. Tagesmerkmale

Aus den Rohdaten eines Tages berechnet `merkmale.py` eine feste Liste von
Kennzahlen. Das ist die Grundlage aller Auswertungen.

| Bereich | Merkmal |
|---|---|
| Umfang | Deep-Work-Zeit, Shallow-Work-Zeit, erfasste Zeit gesamt, Anteil nicht erfasst |
| Zeitpunkte | Beginn des ersten Arbeitsblocks, Ende des letzten |
| Deep Work | Anzahl Deep-Work-Blöcke (direkt anschließende Einträge = ein Block), längster Block, mittlere Blocklänge |
| Zerstückelung | Kategoriewechsel pro Arbeitsstunde, Anzahl Arbeitsblöcke unter 15 min |
| Pausen | Anzahl, Gesamtdauer, Uhrzeit der ersten Pause, längste Strecke ohne Pause (nur Arbeits-Arten) |
| Trinken | Wasser gesamt, Wasser bis 14 Uhr |
| Kontext | Wochentag, Schlaf, Produktivität des Vortags |

Fehlende Werte (zum Beispiel keine Pause, kein Wasser erfasst) sind `None` und fließen nicht
in Mittelwerte ein.

Neue Merkmale sind eine neue Funktion, keine Datenbankänderung.

## 6. Auswertung: schnell zu Ergebnissen

Die Stufen bauen aufeinander auf. Jede ist für sich nützlich.

### Stufe 1, ab Tag 1: Spiegel

- Zeitleiste des Tages mit farbigen Blöcken und sichtbaren Lücken.
- Wochenansicht: Zeitleisten untereinander, daneben Deep-Work-Zeit und beide Scores.

Schon das bewusste Hinschauen verändert Verhalten. Das ist der schnellste
Nutzen und braucht keine Statistik.

### Stufe 2, ab ca. 14 bewerteten Tagen: Gute gegen schlechte Tage

Die Tage werden nach einer wählbaren Zielgröße (Produktivität oder Zufriedenheit) in ein
oberes und ein unteres Drittel geteilt. Sortiert wird nach dem Effekt (Differenz der
Gruppenmittel geteilt durch die Streuung des Merkmals über alle Tage). Für
jedes Merkmal zeigt die App den Mittelwert beider Gruppen nebeneinander:

> An deinen besten Tagen: erste Pause um 10:40, längster Deep-Work-Block 95 min.
> An deinen schwächsten Tagen: erste Pause um 12:50, längster Deep-Work-Block 40 min.

Das ist robust, braucht wenig Daten und ist sofort verständlich.

### Stufe 3, ab ca. 30 Tagen: Korrelationen mit Vorsicht

- Spearman-Korrelation jedes Merkmals mit Produktivität bzw. Zufriedenheit (rangbasiert, unempfindlich
  gegen Ausreißer).
- Angezeigt werden nur Merkmale mit |r| ≥ 0,3, immer mit der Anzahl Tage.
- Formuliert als Hypothese, nie als Befund: „Möglicher Zusammenhang“.
- Hinweis gegen Zufallstreffer: Bei 20 Merkmalen ist rein zufällig etwa eines
  auffällig. Deshalb geht Stufe 3 direkt in Stufe 4 über.

### Stufe 4, laufend: Selbstexperimente

Korrelation sagt nicht, was wirkt. Ein Experiment schon, und es geht schneller
als passives Sammeln.

- Ich lege eine Regel fest, zum Beispiel „Erste Pause vor 11 Uhr“, und einen
  Zeitraum von zwei Wochen.
- Die App vergleicht die Scores im Experimentzeitraum mit den zwei Wochen davor
  und zeigt, an wie vielen Tagen ich die Regel eingehalten habe.
- Dafür kommt ein kleines Modell `Experiment(titel, regel, start, ende)` dazu.

### Später, optional

- **Wochenbericht per LLM:** Die Tagesmerkmale der Woche gehen als Tabelle an
  ein Sprachmodell, das einen kurzen Rückblick mit Auffälligkeiten schreibt.
  Wenig Aufwand, aber nur ein Formulierungshelfer, nicht die Statistik selbst.
- **Regression über mehrere Merkmale** ab etwa 90 Tagen, um Merkmale
  auseinanderzuhalten, die gemeinsam auftreten.
- **CSV-Export** für eigene Auswertungen im Notebook.

### Regeln für saubere Daten

- Beide Scores werden abgegeben, **bevor** man die Statistik des Tages sieht (auch die
  Deep-Work-Zeit der Wochenansicht erscheint erst nach der Bewertung).
- Die Score-Fragen bleiben immer gleich formuliert: „Wie produktiv war der Tag?“ und
  „Wie zufrieden bist du mit dem Tag?“.
- Tage ohne Bewertung fließen nicht in die Auswertung ein.

## 7. Oberfläche

| Seite | Zweck |
|---|---|
| **Jetzt** (Startseite) | Laufender Block mit Dauer, darunter große Knöpfe der häufigsten Kategorien, „Pause“, „Stopp“, „+250 ml Wasser“ |
| **Heute** | Zeitleiste, Einträge bearbeiten, Lücken füllen |
| **Tagesabschluss** | Produktivität und Zufriedenheit (je 1–10), Schlaf, Notiz. Danach die Zusammenfassung des Tages |
| **Plan** | Wochenkalender: Planblöcke ziehen und verschieben, Ist gestreift daneben |
| **Woche** | Zeitleisten untereinander mit Deep-Work-Zeit und beiden Scores |
| **Muster** | Stufen 2 und 3, sobald genug Daten da sind (Umschalter Produktivität/Zufriedenheit). Vorher: „Noch 6 bewertete Tage bis zur ersten Auswertung“ |
| **Admin** | Kategorien pflegen, Daten korrigieren |

## 8. Umsetzung in Phasen

### Phase 0: Aufräumen und Grundgerüst

- Alten Code aus diesem Branch entfernen. Er bleibt auf `master` erhalten.
- Neues Django-5.2-Projekt mit `uv`, `ruff`, `pytest`, Konfiguration per
  Umgebungsvariablen.
- README mit Start-Anleitung.

### Phase 1: Erfassen (MVP)

- Modelle `Kategorie`, `Eintrag`, `Messung`, `Tagesbewertung` mit Admin.
- Seiten „Jetzt“, „Heute“, „Tagesabschluss“.
- Login, PWA-Manifest, Deployment auf dem Server.
- Tests für Timer-Logik (nur ein laufender Eintrag, Wechsel beendet den alten)
  und Tagesgrenze.

**Danach sofort täglich nutzen.** Jeder Tag ohne Erfassung verschiebt die
Auswertung.

### Phase 2: Spiegel und erste Muster (nach ca. 2 Wochen Daten) – umgesetzt

- `merkmale.py` mit Tests.
- Wochenansicht.
- Vergleich gute gegen schlechte Tage.
- Testdaten per `manage.py demodaten` mit eingebautem Muster.
- Betrieb: Docker (gunicorn, WhiteNoise, SQLite-Volume) und CI.

### Phase 3: Hypothesen und Experimente (nach ca. 4 Wochen)

- Korrelationsansicht mit den Vorsichtsregeln.
- Modell und Ansicht für Experimente.

### Phase 4: Plan vs. Ist – umgesetzt (vorgezogen vor Phase 3)

Idee aus dem Prototyp von 2021: Ist/Soll. Ich plane Zeitblöcke und sehe, wie weit das Erfasste
davon abweicht.

- Modell `Planblock(nutzer, kategorie, start, ende, titel)`, überschneidungsfrei pro Nutzer
  (gleiche Regel wie bei Einträgen, gemeinsame Hilfsfunktion in `forms.py`).
- Seite „Plan“ (`/plan/`): Wochenkalender mit FullCalendar 6 (feste Version per CDN), Planblöcke
  per Ziehen anlegen, verschieben, Größe ändern, löschen; Ist-Einträge gestreift daneben.
  Änderungen per `fetch` mit CSRF-Token, der Server validiert mit einem Django-Form.
- Tagesansicht: je Kategorie-Art geplant gegen erfasst (`plan.py`, reine Funktion, schneidet an
  der Tagesgrenze 04:00 ab). Keine Score-Statistik, daher immer sichtbar.
- Noch offen: Abweichung als Merkmal für die Auswertung, Soll je Wochentag als Vorlage.

### Phase 4b: API und MCP – umgesetzt

Ziel: KI-Assistenten (Claude Code, Claude Desktop) bedienen die Zeiterfassung per Sprache.

- Modell `ApiToken(nutzer, name, token_hash, erstellt, zuletzt_genutzt)`. Das Token
  (`zt_` + 256 Bit Zufall) wird nur als SHA-256-Hash gespeichert und genau einmal angezeigt.
  Verwaltung auf der Seite „Einstellungen“ (`/einstellungen/`): erzeugen, auflisten, widerrufen.
- JSON-API unter `/api/v1/` in `tracking/api.py`, plain Django ohne DRF. Auth nur per
  `Authorization: Bearer <token>`; Session-Cookies zählen dort nie (deshalb ist `csrf_exempt`
  sicher). Fehler als `{"fehler": …, "felder": {…}}`. Validierung und Auswertung kommen aus
  `EintragForm`, `BewertungForm`, `PlanblockForm`, `services.py`, `merkmale.py`, `auswertung.py`;
  die Seiten-Views und die API teilen sich dieselben Hilfsfunktionen (`_woche_daten`,
  `_muster_kontext`, `_planbloecke`). Endpunkte: `jetzt`, `start`, `stopp`, `messung`,
  `eintraege` (nachtragen), `tag/<datum>`, `tag/<datum>/bewertung`, `woche/<datum>`, `muster`,
  `plan` (GET, POST), `plan/<id>` (DELETE).
- Die Regeln gelten unverändert: Tagesmerkmale erst nach der Bewertung (Score vor Statistik),
  keine überlappenden Einträge, alles nutzergefiltert (fremde IDs: 404), Muster ab `MIN_TAGE`.
- MCP-Server `mcp_server/server.py` (offizielles Python-SDK `mcp`, FastMCP, Dependency-Group
  `mcp`, nicht in den Produktionsabhängigkeiten). Zwölf Tools mit deutschen Beschreibungen, die
  die API per `urllib` aufrufen. stdio ist Standard; `--http` bindet nur an 127.0.0.1.
- Abweichungen: Das Token erscheint nach dem POST ohne Redirect, damit der Klartext nie in
  Session oder Datenbank landet. Das SDK ist auf `mcp<2` begrenzt (v2 hat FastMCP umbenannt).
  Kein Rate-Limiting (Einzelnutzer hinter Cloudflare Access); Upgrade-Pfad steht in `api.py`.
- Noch offen: Einträge und Messungen per API löschen (bisher nur in der Oberfläche).

### Phase 5: Optional

- Wochenbericht per LLM, CSV-Export, Regression.

## 9. Bewusst nicht vorgesehen

- Automatisches Tracking von Apps oder Fenstern am Rechner. Dafür gibt es
  ActivityWatch. Eine Anbindung wäre später als Import denkbar.
- Mehrmandantenfähigkeit, Teams, Abrechnung.
- Native Handy-App.
- Machine Learning, bevor genug Daten für einfache Statistik da sind.

## 10. Branch-Strategie

- `main` ist der Hauptbranch der Neuentwicklung.
- `archiv-2021` enthält den unveränderten Prototyp (Django, Deep/Shallow Work, zwei Scores,
  Ist/Soll). Daraus stammen die Ideen für Deep Work, zwei Scores und Plan vs. Ist. Nicht ändern.
- `master` bleibt vorerst als Erinnerung an die erste Version von 2020 stehen.
