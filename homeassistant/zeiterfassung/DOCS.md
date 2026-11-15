# Zeiterfassung

Persönliche Zeiterfassung: über den Tag Tätigkeiten, Pausen und Trinkmenge erfassen, abends den
Tag mit zwei Scores (Produktivität, Zufriedenheit) bewerten. Die App zeigt mit der Zeit, welche
Muster gute von schwachen Tagen unterscheiden.

## Installation

1. In Home Assistant **Einstellungen → Add-ons → Add-on-Store → ⋮ → Repositories** öffnen und
   `https://github.com/alexknowsit/time_tracker` hinzufügen.
2. **Zeiterfassung** installieren und starten.
3. Über den Eintrag **Zeiterfassung** in der Seitenleiste öffnen (Ingress, kein Port nötig).

## Anmeldung

Wer Home Assistant bedienen darf, ist in der App automatisch angemeldet. Der Benutzername kommt
von Home Assistant (`X-Remote-User-Name`), beim ersten Aufruf werden Konto und Standardkategorien
angelegt. Jedes Konto hat ein unbrauchbares Passwort und ist in der App Administrator; das
Add-on-Panel sollte daher Administratoren vorbehalten bleiben (Standard). Wer mehrere
Home-Assistant-Nutzer hat, bekommt getrennte Daten je Nutzer.

## Optionen

| Option | Bedeutung |
|---|---|
| `zeitzone` | IANA-Zeitzone für Tagesgrenze und Anzeige, Standard `Europe/Berlin` |
| `csrf_trusted_origins` | Nur falls Speichern mit „CSRF-Prüfung fehlgeschlagen“ scheitert: die Adresse(n), unter denen Home Assistant im Browser aufgerufen wird, mit Schema, z. B. `https://ha.example.org` |

Nach Änderungen das Add-on neu starten.

## Daten und Backup

Alles liegt in `/data` des Add-ons (SQLite-Datei `db.sqlite3` und `secret_key`) und ist damit Teil
der Home-Assistant-Backups. Der Geheimschlüssel wird beim ersten Start erzeugt.

## Sicherheit

Das Add-on veröffentlicht keinen Port. Erreichbar ist es nur über den Supervisor
(Ingress, Adresse `172.30.32.2`), der den Nutzer vorher anmeldet. Deshalb sind beliebige
Host-Header zugelassen (`ALLOWED_HOSTS = *`) und nur Anfragen von dieser Adresse dürfen
Ingress-Pfad, Host und Benutzernamen vorgeben. Alle anderen Anfragen werden behandelt wie bei
einem normalen Server: ohne Anmeldung kein Zugriff.

Die JSON-API (`/api/v1/`) und der MCP-Server brauchen einen erreichbaren Port; das Add-on bietet
ihn bewusst nicht an.
