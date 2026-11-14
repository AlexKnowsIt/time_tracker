from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from tracking.models import Kategorie

STANDARD = [
    ("Fokus", Kategorie.Art.FOKUS, "#2a5db0"),
    ("Meetings", Kategorie.Art.ROUTINE, "#8a5a00"),
    ("Mails", Kategorie.Art.ROUTINE, "#6b4fa0"),
    ("Pause", Kategorie.Art.PAUSE, "#1d7a4d"),
    ("Sport", Kategorie.Art.PRIVAT, "#b3402a"),
    ("Privat", Kategorie.Art.PRIVAT, "#5c6670"),
]


class Command(BaseCommand):
    help = "Legt die Standardkategorien für einen Nutzer an (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, username, **options):
        try:
            nutzer = get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist:
            raise CommandError(f"Nutzer {username!r} existiert nicht.") from None
        neu = 0
        for name, art, farbe in STANDARD:
            _, angelegt = Kategorie.objects.get_or_create(
                nutzer=nutzer, name=name, defaults={"art": art, "farbe": farbe}
            )
            neu += angelegt
        self.stdout.write(f"{neu} Kategorien angelegt, {len(STANDARD) - neu} waren schon da.")
