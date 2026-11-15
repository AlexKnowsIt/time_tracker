"""Anmeldung der Windows-App: ein einmaliges Geheimnis loggt den lokalen Nutzer ein.

Die Server-Schleife läuft im selben Prozess wie das Fenster. `desktop/start.py` erzeugt das
Geheimnis und registriert es hier; der Link `/desktop-anmeldung/<geheimnis>/` gilt genau einmal.
Andere lokale Prozesse kennen das Geheimnis nicht und kommen nicht hinein.
"""

import secrets
import threading

from django.conf import settings
from django.contrib.auth import login
from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache

from .lokal import lokaler_nutzer

LOKALER_NUTZER = "lokal"

_sperre = threading.Lock()
_geheimnis = None


def geheimnis_registrieren(geheimnis):
    global _geheimnis
    with _sperre:
        _geheimnis = geheimnis


def _einloesen(kandidat):
    """True genau einmal, wenn der Kandidat zum registrierten Geheimnis passt."""
    global _geheimnis
    with _sperre:
        if _geheimnis is None or not secrets.compare_digest(_geheimnis, kandidat):
            return False
        _geheimnis = None
        return True


@never_cache
def anmeldung(request, geheimnis):
    if settings.ZEITERFASSUNG_MODUS != "desktop" or not _einloesen(geheimnis):
        raise Http404
    login(
        request,
        lokaler_nutzer(LOKALER_NUTZER),
        backend="django.contrib.auth.backends.ModelBackend",
    )
    return redirect("jetzt")
