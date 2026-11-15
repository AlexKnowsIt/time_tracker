"""Betriebsmodus (Server, Home-Assistant-Add-on, Windows-App) – reine Hilfsfunktionen für settings.

Ohne Zugriff auf Modelle, damit settings.py sie früh nutzen kann.
"""

import json
import os
import secrets
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ImproperlyConfigured

MODI = ("server", "homeassistant", "desktop")
HA_OPTIONEN = Path("/data/options.json")
STANDARD_ZEITZONE = "Europe/Berlin"


def erkenne_modus(umgebung=os.environ, ha_optionen=HA_OPTIONEN):
    """`ZEITERFASSUNG_MODUS` gewinnt. Sonst gilt „homeassistant“, wenn /data/options.json existiert.

    Das Supervisor-Add-on kann keine Umgebungsvariablen setzen, schreibt aber immer diese Datei.
    """
    modus = umgebung.get("ZEITERFASSUNG_MODUS", "").strip().lower()
    if not modus:
        return "homeassistant" if ha_optionen.is_file() else "server"
    if modus not in MODI:
        raise ImproperlyConfigured(f"ZEITERFASSUNG_MODUS {modus!r} unbekannt, erlaubt: {MODI}.")
    return modus


def optionen_laden(pfad=HA_OPTIONEN):
    """Liest und prüft die Add-on-Optionen (`zeitzone`, `csrf_trusted_origins`)."""
    try:
        roh = json.loads(Path(pfad).read_text(encoding="utf-8"))
    except FileNotFoundError:
        roh = {}
    zeitzone = str(roh.get("zeitzone") or STANDARD_ZEITZONE)
    try:
        ZoneInfo(zeitzone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ImproperlyConfigured(
            f"Option zeitzone {zeitzone!r} ist keine IANA-Zeitzone."
        ) from None
    ursprunege = [str(o).strip().rstrip("/") for o in roh.get("csrf_trusted_origins") or []]
    for o in ursprunege:
        if not o.startswith(("http://", "https://")):
            raise ImproperlyConfigured(
                f"csrf_trusted_origins: {o!r} braucht ein Schema (https://…)."
            )
    return {"zeitzone": zeitzone, "csrf_trusted_origins": ursprunege}


def geheimnis_laden(pfad):
    """Liest den SECRET_KEY aus der Datei oder erzeugt ihn beim ersten Start (Rechte 600)."""
    pfad = Path(pfad)
    try:
        wert = pfad.read_text(encoding="utf-8").strip()
        if wert:
            return wert
    except FileNotFoundError:
        pass
    pfad.parent.mkdir(parents=True, exist_ok=True)
    wert = secrets.token_urlsafe(64)
    # O_EXCL: nie eine bestehende Datei überschreiben; 0o600 schon beim Anlegen (unter Windows
    # wirkungslos, dort schützt das Nutzerprofil)
    try:
        fd = os.open(pfad, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:  # ein zweiter Start war schneller
        return pfad.read_text(encoding="utf-8").strip()
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(wert)
    return wert
