"""Home-Assistant-Add-on: Ingress-Präfix, Host-Weitergabe, Anmeldung über HA, statische URLs.

Ingress-Anfragen kommen ausschließlich vom Supervisor (172.30.32.2) und tragen den Pfad, unter dem
HA die App einhängt, im Header `X-Ingress-Path` (`/api/hassio_ingress/<token>`); das Präfix ist
schon vom Pfad abgezogen. Alle Header gelten nur, wenn die Verbindung vom Supervisor kommt, und
die Middlewares stehen nur im HA-Modus in `MIDDLEWARE`.
"""

import json
import re

from django.conf import settings
from django.contrib.auth import login
from django.contrib.staticfiles.storage import StaticFilesStorage
from django.urls import get_script_prefix, set_script_prefix
from whitenoise.storage import CompressedManifestStaticFilesStorage

from .lokal import lokaler_nutzer, sauberer_name

SUPERVISOR_IP = "172.30.32.2"
_PRAEFIX = re.compile(r"/[\w./-]*")  # kein Schema, keine Anführungszeichen, keine Leerzeichen


def _vom_supervisor(request):
    ip = getattr(settings, "ZEITERFASSUNG_INGRESS_IP", SUPERVISOR_IP)
    return request.META.get("REMOTE_ADDR") == ip


def _praefix(request):
    roh = request.META.get("HTTP_X_INGRESS_PATH", "").rstrip("/")
    if roh and _PRAEFIX.fullmatch(roh) and "//" not in roh and ".." not in roh:
        return roh
    return ""


class IngressMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        praefix = ""
        if _vom_supervisor(request):
            praefix = _praefix(request)
            host = request.META.get("HTTP_X_FORWARDED_HOST")
            if host:  # Host des Browsers, sonst scheitert die CSRF-Ursprungsprüfung
                request.META["HTTP_HOST"] = host.split(",")[0].strip()
            request.META["SCRIPT_NAME"] = praefix
            request.path = praefix + request.path_info
            set_script_prefix(praefix + "/")
        response = self.get_response(request)
        if praefix and response.get("Content-Type", "").startswith("application/manifest+json"):
            daten = json.loads(response.content)
            daten["start_url"] = daten["scope"] = praefix + "/"
            response.content = json.dumps(daten)
        return response


class HaAnmeldungMiddleware:
    """Der Supervisor hat den Nutzer schon angemeldet: ihn als lokalen Nutzer einloggen.

    Ohne das gäbe es im Add-on keinen Weg, ein Konto anzulegen. Der Name kommt aus
    `X-Remote-User-Name` (vom Supervisor gesetzt), sonst „ha“. API-Pfade bleiben Bearer-only.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            not request.user.is_authenticated
            and _vom_supervisor(request)
            and not request.path_info.startswith("/api/")
        ):
            name = sauberer_name(request.META.get("HTTP_X_REMOTE_USER_NAME"), "ha")
            login(
                request,
                lokaler_nutzer(name),
                backend="django.contrib.auth.backends.ModelBackend",
            )
        return self.get_response(request)


class _PraefixMixin:
    """Statische URLs mit dem Ingress-Präfix der aktuellen Anfrage (STATIC_URL ist „/static/“)."""

    def url(self, name, *args, **kwargs):
        return get_script_prefix().rstrip("/") + super().url(name, *args, **kwargs)


class IngressStaticFilesStorage(_PraefixMixin, StaticFilesStorage):
    pass


class IngressManifestStorage(_PraefixMixin, CompressedManifestStaticFilesStorage):
    pass
