"""Testdaten mit eingebautem Muster, damit „Muster“ etwas zu zeigen hat.

Eingebaut (alles plus Rauschen):
- Produktivität: frühe erste Pause, lange Deep-Work-Blöcke und mehr Wasser steigern sie,
  unterbrochene Arbeitsblöcke und Wochenenden senken sie, gut geschlafene Nächte heben sie leicht.
- Zufriedenheit: mehr Pausen, weniger Kategoriewechsel und Fortschritt heben sie.
- Fortschritt hängt mit langen Deep-Work-Blöcken zusammen.
- Ein später letzter Kaffee senkt den Schlaf der folgenden Nacht; früher Feierabend hilft beim
  Abschalten, und gutes Abschalten hebt den Schlaf.
Werktage sind immer dabei, Wochenenden nur manchmal (damit es genug bewertete Tage gibt).

Dazu (ab 28 Tagen): Bett- und Aufstehzeiten, einige nachgetragene Einträge, Planblöcke der
letzten 28 Tage mit typischer Unterschreitung (Deep Work etwa 70 % des Plans), ein beendetes
Experiment „Mikropausen“ (20 Tage, tageweise zufällig, eingebauter Effekt auf die Zufriedenheit
an eingehaltenen B-Tagen) und ein laufendes „Koffein-Schluss“ (2-Tages-Blöcke).
"""

import random
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from tracking import experimente
from tracking.models import (
    Eintrag,
    Experiment,
    ExperimentTag,
    Kategorie,
    Messung,
    Planblock,
    Tagesbewertung,
)
from tracking.services import lege_standardkategorien_an, starte_experiment
from tracking.zeit import tagesdatum


def _zu_eins(wert, mitte, halbe_breite):
    """Skaliert auf grob -1..1."""
    return (wert - mitte) / halbe_breite


ARBEIT = {"Deep Work", "Mails", "Meetings", "Organisation"}
FORTSCHRITTE = [
    "Konzept fertig gestellt",
    "Schwieriges Problem gelöst",
    "Entwurf abgegeben",
    "Lange offene Aufgabe erledigt",
    "Plan für die Woche steht",
]


def _laengster_deepwork(plan):
    """Längster Deep-Work-Block in Minuten (direkt anschließende Einträge zählen zusammen)."""
    laengster = aktuell = ende = 0
    for name, von, bis in plan:
        if name != "Deep Work":
            continue
        aktuell = aktuell + bis - von if von == ende else bis - von
        ende = bis
        laengster = max(laengster, aktuell)
    return laengster


EXPERIMENT_MIN_TAGE = 28  # darunter keine Experimente und Planblöcke
MIKROPAUSEN_EFFEKT = 2.5  # Zufriedenheit an eingehaltenen B-Tagen
PLAN_TAGE = 28
DEEPWORK_PLAN_FAKTOR = 0.7  # typische Unterschreitung: erfasst / geplant


def _experiment_felder(vorlage, start):
    v = experimente.VORLAGEN[vorlage]
    return {
        "titel": v["titel"],
        "hypothese": v["hypothese"],
        "regel_wenn": v["wenn"],
        "regel_dann": v["dann"],
        "design": v["design"],
        "blocklaenge": v["blocklaenge"],
        "dauer_tage": v["dauer"],
        "zielgroesse": v["ziel"],
        "start": start,
    }


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
        parser.add_argument("--tage", type=int, default=120, help="Zeitraum bis gestern")
        parser.add_argument("--seed", type=int, default=1)

    @staticmethod
    def _planbloecke(nutzer, kategorien, plan_tage, gestern, zeit, rng):
        """Planblöcke der letzten 28 Tage: Deep Work wird zu etwa 70 % geschafft, Shallow Work
        fast ganz. Der Plan ergibt sich rückwärts aus dem Erfassten, damit der Faktor stimmt."""
        if len(plan_tage) == 0:
            return []
        erster = gestern - timedelta(days=PLAN_TAGE - 1)
        bloecke = []
        for tag, (plan, start) in plan_tage.items():
            if tag < erster:
                continue
            ist = {"Deep Work": 0, "Mails": 0}
            for name, von, bis in plan:
                if name == "Deep Work":
                    ist["Deep Work"] += bis - von
                elif name in ("Mails", "Meetings"):
                    ist["Mails"] += bis - von
            minute = start
            for name, faktor, streuung in (
                ("Deep Work", DEEPWORK_PLAN_FAKTOR, 0.1),
                ("Mails", 0.95, 0.12),
            ):
                if not ist[name]:
                    continue
                verhaeltnis = min(1.3, max(0.45, rng.gauss(faktor, streuung)))
                laenge = max(15, round(ist[name] / verhaeltnis / 5) * 5)
                bloecke.append(
                    Planblock(
                        nutzer=nutzer,
                        kategorie=kategorien[name],
                        start=zeit(tag, minute),
                        ende=zeit(tag, minute + laenge),
                    )
                )
                minute += laenge
        return bloecke

    def handle(self, *args, username, tage, seed, **options):
        if tage < 1:
            raise CommandError("--tage muss mindestens 1 sein.")
        User = get_user_model()
        nutzer = User.objects.filter(username=username).first()
        if nutzer and any(
            m.objects.filter(nutzer=nutzer).exists()
            for m in (Eintrag, Messung, Tagesbewertung, Planblock, Experiment)
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

            # Neues (eigener Zufallsstrom, damit die übrigen Testdaten unverändert bleiben)
            rng2 = random.Random(seed * 7919 + 13)
            zusatz = random.Random(seed * 104729 + 7)
            heute = gestern + timedelta(days=1)
            mikro_effekt, koffein_b, experiment_tage = set(), set(), set()
            if tage >= EXPERIMENT_MIN_TAGE:
                mikro = starte_experiment(
                    nutzer,
                    seed=seed + 100,
                    **_experiment_felder("mikropausen", heute - timedelta(days=26)),
                )
                mikro.status = Experiment.Status.BEENDET  # nur ein Experiment läuft gleichzeitig
                mikro.save(update_fields=["status"])
                koffein = starte_experiment(
                    nutzer,
                    seed=seed + 200,
                    **_experiment_felder("koffein_schluss", heute - timedelta(days=6)),
                )
                tags = []
                for experiment in (mikro, koffein):
                    for t in experiment.tage.all():
                        if t.datum >= heute:
                            continue
                        t.eingehalten = rng2.random() < (0.85 if t.bedingung == "B" else 0.95)
                        tags.append(t)
                        if t.bedingung == "B" and t.eingehalten:
                            (mikro_effekt if experiment is mikro else koffein_b).add(t.datum)
                ExperimentTag.objects.bulk_update(tags, ["eingehalten"])
                experiment_tage = {t.datum for t in tags}  # Experimenttage immer erfasst
            plan_tage = {}
            kaffee_vortag, abgeschaltet_vortag = None, None  # wirken auf die folgende Nacht
            for i in range(tage):
                tag = gestern - timedelta(days=tage - 1 - i)
                wochenende = tag.weekday() >= 5
                r = rng  # Zufallsstrom dieses Tages
                if wochenende and rng.random() > 0.35:
                    if tag not in experiment_tage:
                        continue
                    r = zusatz  # eigener Strom: die übrigen Tage bleiben unverändert
                plan, start, ende, erste_pause, pausen_n, deep_mittel, zerstueck = _tagesplan(r)
                unterbrechung = r.random() * 0.45  # Neigung zu Unterbrechungen an diesem Tag
                arbeit_n = unterbrochen_n = 0
                for name, von, bis in plan:
                    arbeit = name in ARBEIT
                    unterbrochen = arbeit and r.random() < unterbrechung * (
                        1 if name == "Deep Work" else 0.5
                    )
                    abgeschlossen = None
                    if arbeit and r.random() < 0.6:
                        abgeschlossen = r.random() < 0.45 + 0.4 * (bis - von >= 45)
                    arbeit_n += arbeit
                    unterbrochen_n += unterbrochen
                    eintraege.append(
                        Eintrag(
                            nutzer=nutzer,
                            kategorie=kategorien[name],
                            start=zeit(tag, von),
                            ende=zeit(tag, bis),
                            abgeschlossen=abgeschlossen,
                            unterbrochen=unterbrochen,
                            nachgetragen=rng2.random() < 0.15,
                        )
                    )
                plan_tage[tag] = (plan, start)
                anteil_unterbrochen = unterbrochen_n / arbeit_n if arbeit_n else 0
                glaeser = r.randint(3, 12)
                for _ in range(glaeser):
                    messungen.append(
                        Messung(
                            nutzer=nutzer,
                            zeitpunkt=zeit(tag, r.randrange(start, ende)),
                            typ=Messung.Typ.WASSER_ML,
                            menge=250,
                        )
                    )
                kaffee_n = r.choice([0, 1, 2, 2, 3, 4])
                letzter_kaffee = r.randrange(9 * 60, 18 * 60 + 1, 15) if kaffee_n else None
                if (
                    tag in koffein_b and letzter_kaffee is not None
                ):  # Regel: kein Kaffee nach 14 Uhr
                    letzter_kaffee = min(letzter_kaffee, 14 * 60)
                for k in range(kaffee_n):
                    uhr = letzter_kaffee if k == 0 else r.randrange(8 * 60, letzter_kaffee + 1)
                    messungen.append(
                        Messung(
                            nutzer=nutzer,
                            zeitpunkt=zeit(tag, uhr),
                            typ=Messung.Typ.KAFFEE,
                            menge=1,
                        )
                    )
                # Nacht vor dem Tag: später Kaffee und schlechtes Abschalten am Vortag kosten Schlaf
                schlaf = 7.3 + r.gauss(0, 0.5)
                if kaffee_vortag is not None:
                    schlaf -= 1.4 * _zu_eins(kaffee_vortag, 15 * 60, 4 * 60)
                if abgeschaltet_vortag is not None:
                    schlaf += 0.3 * (abgeschaltet_vortag - 3)
                schlaf = min(10, max(4, round(schlaf * 2) / 2))
                laengster = _laengster_deepwork(plan)
                fortschritt = r.random() < (0.85 if laengster >= 75 else 0.25)
                produktiv = (
                    5.5
                    + 1.8 * _zu_eins(12 * 60, erste_pause, 90)  # früh = gut
                    + 1.6 * _zu_eins(deep_mittel, 72, 38)
                    + 1.0 * _zu_eins(glaeser, 7.5, 4.5)
                    - 5.0 * (anteil_unterbrochen - 0.15)  # Unterbrechungen senken
                    + 0.6 * _zu_eins(schlaf, 7, 1.2)
                    - (1.2 if wochenende else 0)
                    + r.gauss(0, 0.8)
                )
                zufrieden = (
                    5.5
                    + 1.2 * _zu_eins(pausen_n, 2.5, 1.5)
                    + 1.8 * _zu_eins(0.5, zerstueck, 0.5)  # weniger Wechsel = gut
                    + (1.3 if fortschritt else -0.9)
                    + 0.15 * (produktiv - 5.5)
                    + r.gauss(0, 0.8)
                    + (MIKROPAUSEN_EFFEKT if tag in mikro_effekt else 0)
                )
                abgeschaltet = None
                if r.random() < 0.8:
                    abgeschaltet = round(3.4 - 1.2 * _zu_eins(ende, 17 * 60, 90) + r.gauss(0, 0.7))
                    abgeschaltet = min(5, max(1, abgeschaltet))
                aufstehzeit = bettzeit = None
                if rng2.random() < 0.85:  # sonst nur die Stunden, ohne Uhrzeiten
                    aufstehen = start - rng2.randrange(30, 91, 5) + (60 if wochenende else 0)
                    bett = aufstehen - round(schlaf * 60)
                    aufstehzeit = time(aufstehen // 60, aufstehen % 60)
                    bettzeit = time(bett % 1440 // 60, bett % 60)
                bewertungen.append(
                    Tagesbewertung(
                        nutzer=nutzer,
                        datum=tag,
                        produktivitaet=min(10, max(1, round(produktiv))),
                        zufriedenheit=min(10, max(1, round(zufrieden))),
                        fortschritt=fortschritt,
                        fortschritt_notiz=r.choice(FORTSCHRITTE)
                        if fortschritt and r.random() < 0.5
                        else "",
                        abgeschaltet=abgeschaltet,
                        schlaf_h=schlaf,
                        bettzeit=bettzeit,
                        aufstehzeit=aufstehzeit,
                    )
                )
                kaffee_vortag, abgeschaltet_vortag = letzter_kaffee, abgeschaltet
            planbloecke = self._planbloecke(nutzer, kategorien, plan_tage, gestern, zeit, rng2)
            Planblock.objects.bulk_create(planbloecke)
            Eintrag.objects.bulk_create(eintraege)
            Messung.objects.bulk_create(messungen)
            Tagesbewertung.objects.bulk_create(bewertungen)
        if tage >= EXPERIMENT_MIN_TAGE:
            self.stdout.write(
                f"{len(planbloecke)} Planblöcke, Experimente „Mikropausen“ (beendet) und "
                "„Koffein-Schluss“ (läuft)."
            )
        self.stdout.write(
            f"{len(bewertungen)} Tage bis {gestern:%d.%m.%Y}: {len(eintraege)} Einträge, "
            f"{len(messungen)} Messungen (Wasser, Kaffee), {len(bewertungen)} Bewertungen."
        )
