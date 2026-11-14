"""Einstellungen für pytest: Debug an, damit kein SECRET_KEY nötig ist."""

import os

os.environ.setdefault("DJANGO_DEBUG", "1")

from .settings import *  # noqa: E402, F403
