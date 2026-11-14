"""Einstellungen für pytest: Debug an, damit kein SECRET_KEY nötig ist."""

import os

os.environ.setdefault("DJANGO_DEBUG", "1")

from .settings import *  # noqa: E402, F403

# Kein collectstatic-Manifest in Tests, auch wenn DJANGO_DEBUG=0 gesetzt ist.
STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}  # noqa: F405
