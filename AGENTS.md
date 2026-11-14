# AGENTS.md

Hinweise für KI-Agenten (und Menschen), die an diesem Repo arbeiten.

## Worum es geht

Persönliche Zeiterfassung: Über den Tag Tätigkeiten, Pausen und Trinkmenge
erfassen, abends den Tag mit einem Score (1–10) bewerten. Die App zeigt mit der
Zeit, welche Muster gute von schwachen Tagen unterscheiden.

Das vollständige Zielbild mit Architektur, Datenmodell und Phasen steht in
`docs/zielbild.md`. Es ist die verbindliche Referenz. Wer davon abweicht,
begründet es und passt das Zielbild an.

## Stack und Befehle

- Python 3.13, Django 5.2 LTS, HTMX 2 per CDN, SQLite (WAL). Kein JS-Framework,
  kein Build-Schritt.
- Abhängigkeiten mit `uv`. Neue Abhängigkeiten nur mit gutem Grund.
- Statistik mit der Standardbibliothek (`statistics`), solange es reicht.

```bash
uv sync
export DJANGO_DEBUG=1
uv run python manage.py migrate
uv run pytest
uv run ruff check && uv run ruff format
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py demodaten demo   # Testdaten, nur für leere Nutzer
```

## Struktur

- Eine App `tracking`. Erst aufteilen, wenn ein Teil wirklich eigenständig wird.
- `zeit.py`, `merkmale.py`, `auswertung.py`: reine Funktionen ohne DB-Zugriff,
  damit sie einfach testbar sind.
- `services.py`: Timer-Logik (höchstens ein laufender Eintrag pro Nutzer).
- Bezeichner, Kommentare, Commits und Doku auf Deutsch.

## Regeln, die sich bewährt haben

Diese Punkte sind in Reviews aufgefallen und gelten für jede Änderung:

- **Jede Abfrage nach `nutzer` filtern.** Objekte aus der URL oder aus
  Formularen immer mit `get_object_or_404(..., nutzer=request.user)` holen.
  Formular-Querysets (z. B. Kategorien) auf den Nutzer einschränken.
- **Keine überlappenden Zeiteinträge.** Überschneidungen verfälschen die
  Auswertung (doppelt gezählte Zeit). Prüfung in `EintragForm.clean`.
- **Fehleingaben müssen korrigierbar sein.** Alles, was man per Tipp anlegen
  kann, muss man in der Oberfläche auch löschen können. Löschen mit Rückfrage.
- **Nach POST immer Redirect** (PRG). HTMX bekommt Teil-Templates, ohne JS
  funktioniert ein normaler POST.
- **Score vor Statistik.** Die Zusammenfassung eines Tages erscheint erst nach
  der Bewertung. Die Score-Frage bleibt immer gleich formuliert.
- **Tagesgrenze 04:00 Uhr** über `tagesdatum()`/`tagesgrenzen()`, nie selbst
  rechnen. Zeitzone nur über `settings.TIME_ZONE`, nie hart codieren.
- **Pausen werden aktiv erfasst.** Lücken sind „nicht erfasst“, keine Pause.
- **Echte und Testdaten nie mischen.** `demodaten` bricht ab, wenn der Nutzer
  schon Daten hat.
- **Keine Geheimnisse im Repo.** `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`,
  `DJANGO_ALLOWED_HOSTS`, `DJANGO_DB_PATH` kommen aus der Umgebung.
- **Keine N+1-Abfragen** in Listen- und Wochenansichten; mit
  `django_assert_max_num_queries` testen.
- **Auswertungen als Hypothesen formulieren**, nie als Ursache. Mindestanzahl
  Tage beachten (`auswertung.MIN_TAGE`).

## Arbeitsweise

- Faul, nicht schlampig: erst prüfen, ob es gebraucht wird, ob es das schon
  gibt, ob Stdlib oder Django es können. Dann minimaler Code. Löschen vor
  Hinzufügen. Bewusste Abkürzungen mit `ponytail:`-Kommentar (Grenze und
  Upgrade-Pfad).
- Nie sparen bei Validierung, Schutz vor Datenverlust, Sicherheit und
  Barrierefreiheit.
- Nicht-triviale Logik bekommt einen Test.
- Vor jedem Commit: pytest grün, ruff sauber, keine fehlenden Migrationen.
- UI-Änderungen mit Playwright-Screenshots bei 390 px Breite prüfen.
  Screenshots für das README liegen in `docs/screenshots/`.

## Zusammenarbeit mit Subagenten

Bewährtes Vorgehen in diesem Projekt:

- Ein Orchestrator plant, schreibt präzise Aufträge und prüft. Subagenten
  (Sonnet) setzen die Programmieraufgaben um.
- Aufträge nennen: zu lesende Dateien und Zielbild-Abschnitte, konkrete
  Akzeptanzkriterien, Tests, was nicht angefasst werden darf, „nicht pushen“,
  kurze Rückmeldung.
- Aufgaben, die dieselben Dateien berühren, nacheinander statt parallel.
- Der Orchestrator liest den Diff selbst, führt die Tests selbst aus und schaut
  Screenshots an, bevor er pusht. Nachbesserungen gehen an denselben Subagenten
  zurück, weil er den Kontext schon hat.

## Branches

- `main`: Hauptbranch der Neuentwicklung.
- `archiv-2020` (und vorerst `master`): unveränderter Stand des ersten
  Versuchs von 2020. Nicht ändern.

## Stand

- Phase 0 und 1 umgesetzt: Grundgerüst, Modelle, Seiten „Jetzt“, „Heute“,
  „Tagesabschluss“, Login, PWA-Manifest.
- Phase 2 (Tagesmerkmale, Woche, Vergleich guter und schwacher Tage, Testdaten):
  siehe `docs/zielbild.md`.
- Offen: Deployment, Phase 3 (Korrelationen, Selbstexperimente).
