"""Lokaler Nutzer für Windows-App und Home-Assistant-Add-on (Anmeldung ohne Passwort)."""

import re

from django.contrib.auth import get_user_model
from django.core.management import call_command


def lokaler_nutzer(benutzername):
    """Holt den Nutzer oder legt ihn an: Superuser, unbrauchbares Passwort, Standardkategorien."""
    modell = get_user_model()
    nutzer, neu = modell.objects.get_or_create(
        **{modell.USERNAME_FIELD: benutzername},
        defaults={"is_staff": True, "is_superuser": True},
    )
    if neu:
        nutzer.set_unusable_password()
        nutzer.save()
        call_command("standardkategorien", benutzername, verbosity=0)
    return nutzer


def sauberer_name(roh, standard):
    """Aus einem fremden Namen (HA-Header) einen harmlosen Benutzernamen machen."""
    name = re.sub(r"[^\w.@+-]", "", roh or "", flags=re.ASCII)[:150]
    return name or standard
