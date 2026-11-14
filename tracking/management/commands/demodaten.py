"""Testdaten mit eingebautem Muster, damit „Muster“ etwas zu zeigen hat.

Eingebaut: frühe erste Pause, lange Deep-Work-Blöcke und mehr Wasser erhöhen die Produktivität;
mehr Pausen und weniger Kategoriewechsel erhöhen die Zufriedenheit. Dazu Rauschen.
"""

import random
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tracking.models import Eintrag, Kategorie, Messung, Tagesbewertung
from tracking.services import lege_standardkategorien_an
from tracking.zeit import tagesdatum


def _zu_eins(wert, mitte, halbe_breite):
    """Skaliert auf grob -1..1."""
    return (wert - mitte) / halbe_breite


def _tagesplan(rng):
    """Zufällige Tagesform als Minutenliste [(kategoriename, start_min, ende_min)] plus Latentes."""
    start = rng.randrange(7 * 60 + 30, 9 * 60 + 31, 5)
    ende = start + rng.randrange(7 * 60 + 30, 9 * 60 + 31, 5)
    erste_pause = rng.randrange(9 * 60 + 30, 13 * 60 + 31, 5)
    pausen_n = rng.randint(1, 4)
    deep_mittel = rng.uniform(35, 110)
    zerstueckelung = rng.random()  # 0 = ruhig, 1 = viele kurze Wechsel

    pause_zeiten = [erste_pause] + [
        erste_pause + i * rng.randrange(100, 160, 5) for i in range(1, pausen_n)
    ]
    plan, t = [], start
    while t < ende:
        if pause_zeiten and t >= pause_zeiten[0]:
            pause_zeiten.pop(0)
            lang = (
                rng.randrange(30, 46, 5)
                if 11 * 60 + 30 <= t <= 14 * 60
                else rng.randrange(10, 26, 5)
            )
            plan.append(("Pause", t, min(t + lang, ende)))
            t += lang
            continue
        if rng.random() < 0.1:  # vergessen zu erfassen: Lücke
            t += rng.randrange(5, 21, 5)
            continue
        if rng.random() < 0.6 - 0.4 * zerstueckelung:
            laenge = max(20, round(rng.gauss(deep_mittel, 15) / 5) * 5)
            name = "Deep Work"
        else:
            kurz = rng.random() < zerstueckelung
            laenge = rng.randrange(5, 15, 5) if kurz else rng.randrange(20, 50, 5)
            name = rng.choice(["Mails", "Meetings", "Organisation"])
        grenze = min(ende, pause_zeiten[0] if pause_zeiten else ende)
        laenge = min(laenge, grenze - t)
        if laenge <= 0:
            continue
        if name == "Deep Work" and laenge >= 60 and rng.random() < 0.3:
            haelfte = laenge // 2 // 5 * 5  # zwei anschließende Einträge = ein Block
            plan += [(name, t, t + haelfte), (name, t + haelfte, t + laenge)]
        else:
            plan.append((name, t, t + laenge))
        t += laenge
    if rng.random() < 0.3:
        plan.append(("Sport", ende + 15, ende + 15 + rng.randrange(30, 61, 5)))
    return plan, start, ende, erste_pause, pausen_n, deep_mittel, zerstueckelung


class Command(BaseCommand):
    help = "Erzeugt Testdaten (Einträge, Wasser, Bewertungen) für einen Nutzer ohne Daten."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--tage", type=int, default=42, help="Zeitraum bis gestern")
        parser.add_argument("--seed", type=int, default=1)

    def handle(self, *args, username, tage, seed, **options):
        if tage < 1:
            raise CommandError("--tage muss mindestens 1 sein.")
        User = get_user_model()
        nutzer = User.objects.filter(username=username).first()
        if nutzer and any(
            m.objects.filter(nutzer=nutzer).exists() for m in (Eintrag, Messung, Tagesbewertung)
        ):
            raise CommandError(
                f"Nutzer {username!r} hat schon Daten. Testdaten nie mit echten Daten mischen."
            )
        rng = random.Random(seed)
        with transaction.atomic():
            if not nutzer:
                nutzer = User.objects.create_user(username, password="demo")
                self.stdout.write(f"Nutzer {username!r} angelegt, Passwort: demo")
            lege_standardkategorien_an(nutzer)
            kategorien = {k.name: k for k in Kategorie.objects.filter(nutzer=nutzer)}
            gestern = tagesdatum(timezone.now()) - timedelta(days=1)
            eintraege, messungen, bewertungen = [], [], []

            def zeit(tag, minuten):  # lokale Wanduhr, auch über Mitternacht
                return timezone.make_aware(
                    datetime.combine(tag, time(0)) + timedelta(minutes=minuten)
                )

            for i in range(tage):
                tag = gestern - timedelta(days=tage - 1 - i)
                if tag.weekday() >= 5:
                    continue
                plan, start, ende, erste_pause, pausen_n, deep_mittel, zerstueck = _tagesplan(rng)
                for name, von, bis in plan:
                    eintraege.append(
                        Eintrag(
                            nutzer=nutzer,
                            kategorie=kategorien[name],
                            start=zeit(tag, von),
                            ende=zeit(tag, bis),
                        )
                    )
                glaeser = rng.randint(3, 12)
                for _ in range(glaeser):
                    messungen.append(
                        Messung(
                            nutzer=nutzer,
                            zeitpunkt=zeit(tag, rng.randrange(start, ende)),
                            typ=Messung.Typ.WASSER_ML,
                            menge=250,
                        )
                    )
                produktiv = (
                    5.5
                    + 1.8 * _zu_eins(12 * 60, erste_pause, 90)  # früh = gut
                    + 1.6 * _zu_eins(deep_mittel, 72, 38)
                    + 1.0 * _zu_eins(glaeser, 7.5, 4.5)
                    + rng.gauss(0, 0.8)
                )
                zufrieden = (
                    5.5
                    + 1.2 * _zu_eins(pausen_n, 2.5, 1.5)
                    + 1.8 * _zu_eins(0.5, zerstueck, 0.5)  # weniger Wechsel = gut
                    + 0.15 * (produktiv - 5.5)
                    + rng.gauss(0, 0.8)
                )
                bewertungen.append(
                    Tagesbewertung(
                        nutzer=nutzer,
                        datum=tag,
                        produktivitaet=min(10, max(1, round(produktiv))),
                        zufriedenheit=min(10, max(1, round(zufrieden))),
                        schlaf_h=rng.randrange(11, 18) / 2,
                    )
                )
            Eintrag.objects.bulk_create(eintraege)
            Messung.objects.bulk_create(messungen)
            Tagesbewertung.objects.bulk_create(bewertungen)
        self.stdout.write(
            f"{len(bewertungen)} Werktage bis {gestern:%d.%m.%Y}: {len(eintraege)} Einträge, "
            f"{len(messungen)} Wasser-Messungen, {len(bewertungen)} Bewertungen."
        )
