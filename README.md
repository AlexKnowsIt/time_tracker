# Zeiterfassung

Persönliche Zeiterfassung mit Tagesauswertung. Über den Tag erfasst man Tätigkeiten, Pausen und
Trinkmenge (je ein Tipp), abends bewertet man den Tag mit zwei Scores: Produktivität und
Zufriedenheit. Daraus zeigt die App mit der Zeit, welche Muster gute von schwachen Tagen
unterscheiden. Die Ergebnisse sind Hypothesen („Unterschiede, keine Ursachen“).

Ziel, Architektur und Phasen: [docs/zielbild.md](docs/zielbild.md). Stand: Phase 0 bis 2
umgesetzt (Erfassen, Woche, Muster, Testdaten, Docker/CI). Als Nächstes: Phase 3 (Korrelationen,
Selbstexperimente), danach „Plan vs. Ist“. Der alte Prototyp liegt unverändert im Branch
`archiv-2021`.

## Funktionen

- **Jetzt** (`/`): laufender Eintrag, ein Tipp auf eine Kategorie beendet den alten Block und
  startet den neuen. „Stopp“, „+250 ml Wasser“, „+1 Kaffee“ je ein Tipp.
- **Heute** (`/tag/`, `/tag/JJJJ-MM-TT/`): Zeitleiste (Tag = 04:00 bis 04:00 Uhr, schraffiert =
  nicht erfasst), Einträge bearbeiten, löschen, nachtragen, Messungen. Überschneidungen werden
  abgelehnt.
- **Abschluss** (`/tag/JJJJ-MM-TT/abschluss/`): „Wie produktiv war der Tag?“ und „Wie zufrieden
  bist du mit dem Tag?“ (je 1–10), Schlaf, Notiz. Erst danach erscheint die Zusammenfassung.
- **Woche** (`/woche/`, `/woche/JJJJ-MM-TT/`): Montag bis Sonntag, je Tag Zeitleiste, Deep-Work-
  Zeit und beide Scores.
- **Muster** (`/muster/?ziel=produktivitaet|zufriedenheit`): ab 14 bewerteten Tagen (letzte
  180 Tage) Vergleich des oberen und unteren Drittels nach der gewählten Zielgröße, je Merkmal
  Ø gute gegen Ø schwache Tage, stärkster Unterschied oben. Davor: „Noch N bewertete Tage bis
  zur ersten Auswertung“.
- **Kategorien** haben eine Art: Deep Work, Shallow Work, Organisation, Pause, Freizeit.
  Pflege im Admin; `standardkategorien` legt Deep Work, Mails, Meetings, Organisation, Pause,
  Sport und Freizeit an.
- Auf dem Handy als Web-App installierbar (Manifest). HTMX kommt per CDN.

## Setup lokal

Voraussetzung: [uv](https://docs.astral.sh/uv/).

```
uv sync
export DJANGO_DEBUG=1
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py standardkategorien <benutzername>
uv run python manage.py runserver   # App: http://127.0.0.1:8000/, Admin: /admin/
```

Prüfen vor jedem Commit:

```
uv run pytest
uv run ruff check && uv run ruff format
DJANGO_DEBUG=1 uv run python manage.py makemigrations --check --dry-run
```

## Testdaten

```
uv run python manage.py demodaten demo [--tage 42] [--seed 1]
```

Legt den Nutzer an, falls er fehlt (Passwort `demo`, wird ausgegeben), dazu die Standardkategorien
und für jeden Werktag bis gestern Einträge, Wasser-Messungen und beide Bewertungen. Eingebautes
Muster: frühe erste Pause, lange Deep-Work-Blöcke und mehr Wasser erhöhen die Produktivität;
mehr Pausen und weniger Wechsel erhöhen die Zufriedenheit (plus Rauschen). Mit gleichem `--seed`
immer gleiche Daten. Der Befehl bricht ab, wenn der Nutzer schon Einträge, Messungen oder
Bewertungen hat; echte und Testdaten werden nie gemischt. Am besten mit einer eigenen Datenbank
(`DJANGO_DB_PATH=/tmp/demo.sqlite3`).

## Docker

```
cp .env.example .env     # DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, DJANGO_CSRF_TRUSTED_ORIGINS setzen
docker compose up -d --build
docker compose exec zeiterfassung python manage.py createsuperuser
docker compose exec zeiterfassung python manage.py standardkategorien <benutzername>
```

Der Container führt beim Start `migrate` aus und startet dann gunicorn auf Port 8000. Statische
Dateien liefert WhiteNoise aus, ein zusätzlicher Webserver dafür ist nicht nötig. Die
SQLite-Datei liegt im Volume `daten` unter `/data/db.sqlite3`; Backup = Datei kopieren.

Im Betrieb (`DJANGO_DEBUG` aus) sind Session- und CSRF-Cookie `Secure`, und `X-Forwarded-Proto`
wird vertraut. Die App gehört daher hinter einen HTTPS-Reverse-Proxy (z. B. Cloudflare), der
diesen Header selbst setzt und auf HTTPS umleitet. `manage.py check --deploy` meldet dann nur
noch `W004` (HSTS) und `W008` (SSL-Redirect), beides Aufgabe des Proxys.

## Umgebungsvariablen

| Variable | Bedeutung |
|---|---|
| `DJANGO_SECRET_KEY` | Pflicht, außer bei `DJANGO_DEBUG=1` (dann Dev-Default) |
| `DJANGO_DEBUG` | `1`/`true`/`yes` schaltet Debug ein, Standard: aus |
| `DJANGO_ALLOWED_HOSTS` | Kommagetrennte Hostnamen |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Kommagetrennte Ursprünge mit Schema (`https://…`), nur bei Debug aus |
| `DJANGO_DB_PATH` | Pfad der SQLite-Datei, Standard `db.sqlite3` im Projektordner (Docker: `/data/db.sqlite3`) |

Die CI (`.github/workflows/ci.yml`) führt bei Push und Pull Request auf `main` ruff, pytest und
die Migrationsprüfung aus.
