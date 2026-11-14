# Zeiterfassung

Django-App, um über den Tag Tätigkeiten, Pausen und Trinkmengen zu erfassen und
abends den Tag zu bewerten. Daraus entsteht mit der Zeit eine Auswertung, welche
Muster gute von schlechten Tagen unterscheiden.

Ziel, Architektur und Phasen: [docs/zielbild.md](docs/zielbild.md).
Stand: Phase 1 (Erfassen): Modelle, Admin und Oberfläche für Jetzt, Heute und Tagesabschluss.

## Setup

Voraussetzung: [uv](https://docs.astral.sh/uv/).

```
uv sync
export DJANGO_DEBUG=1
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py python manage.py standardkategorien <benutzername>
uv run python manage.py runserver   # App: http://127.0.0.1:8000/, Admin: /admin/
uv run pytest
uv run ruff check && uv run ruff format
```

## Bedienung

- **Jetzt** (`/`): laufender Eintrag, ein Tipp auf eine Kategorie beendet den alten Block und
  startet den neuen. „Stopp“, „+250 ml Wasser“, „+1 Kaffee“ je ein Tipp. Kategorien sind nach
  Häufigkeit der letzten 30 Tage sortiert.
- **Heute** (`/tag/`, `/tag/JJJJ-MM-TT/`): Zeitleiste (Tag = 04:00 bis 04:00 Uhr, schraffiert =
  nicht erfasst), Einträge bearbeiten, löschen, nachtragen, Messungen. Die Zusammenfassung
  erscheint erst, nachdem der Score gespeichert wurde.
- **Abschluss** (`/tag/JJJJ-MM-TT/abschluss/`): Score 1–10, Energie, Schlaf, Notiz. Erneutes
  Speichern aktualisiert die Bewertung des Tages.
- Kategorien pflegt man im Admin. Für einen neuen Nutzer legt
  `uv run python manage.py standardkategorien <benutzername>` Fokus, Meetings, Mails, Pause,
  Sport und Privat an (idempotent).
- Auf dem Handy über „Zum Startbildschirm hinzufügen“ als Web-App installierbar (Manifest,
  kein Service Worker). HTMX kommt per CDN.

## Umgebungsvariablen

| Variable | Bedeutung |
|---|---|
| `DJANGO_SECRET_KEY` | Pflicht, außer bei `DJANGO_DEBUG=1` (dann Dev-Default) |
| `DJANGO_DEBUG` | `1`/`true`/`yes` schaltet Debug ein, Standard: aus |
| `DJANGO_ALLOWED_HOSTS` | Kommagetrennte Hostnamen |
| `DJANGO_DB_PATH` | Pfad der SQLite-Datei, Standard `db.sqlite3` im Projektordner |
