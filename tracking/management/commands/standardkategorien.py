from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from tracking.services import STANDARDKATEGORIEN, lege_standardkategorien_an


class Command(BaseCommand):
    help = "Legt die Standardkategorien für einen Nutzer an (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, username, **options):
        try:
            nutzer = get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist:
            raise CommandError(f"Nutzer {username!r} existiert nicht.") from None
        neu = lege_standardkategorien_an(nutzer)
        self.stdout.write(
            f"{neu} Kategorien angelegt, {len(STANDARDKATEGORIEN) - neu} waren schon da."
        )
