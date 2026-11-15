"""Plan vs. Ist: reine Funktionen ohne DB-Zugriff."""

from datetime import timedelta
from statistics import median

from .models import Kategorie
from .zeit import tagesdatum


def _minuten(block, beginn, ende, jetzt):
    """Minuten des Blocks innerhalb [beginn, ende). Laufende Blöcke zählen bis jetzt."""
    von = max(block.start, beginn)
    bis = min(block.ende or jetzt, ende)
    return max(0.0, (bis - von).total_seconds() / 60)


def plan_vs_ist(planbloecke, eintraege, beginn, ende, jetzt):
    """Je Kategorie-Art geplante und erfasste Minuten und die Differenz (Ist minus Plan).

    Blöcke, die über die Tagesgrenze (beginn/ende) ragen, werden abgeschnitten.
    Arten ohne Plan und ohne Ist fehlen; Reihenfolge wie Kategorie.Art.
    """
    geplant, erfasst = {}, {}
    for quelle, summen in ((planbloecke, geplant), (eintraege, erfasst)):
        for b in quelle:
            art = b.kategorie.art
            summen[art] = summen.get(art, 0) + _minuten(b, beginn, ende, jetzt)
    zeilen = []
    for art, label in Kategorie.Art.choices:
        if art in geplant or art in erfasst:
            p, i = round(geplant.get(art, 0)), round(erfasst.get(art, 0))
            zeilen.append(
                {"art": art, "label": label, "geplant": p, "erfasst": i, "differenz": i - p}
            )
    return zeilen


PLAN_FAKTOR_TAGE = 28
PLAN_FAKTOR_MIN_TAGE = 5


def plan_faktor(
    planbloecke, eintraege, heute, tage=PLAN_FAKTOR_TAGE, min_tage=PLAN_FAKTOR_MIN_TAGE
):
    """Plan-Faktor je Kategorie-Art (Buehler, Griffin & Ross 1994): Median von Ist/Plan über die
    letzten ``tage`` Tage vor ``heute`` (heute zählt nicht, der Tag ist nicht vorbei).

    Je Tag und Art zählt das Verhältnis erfasster zu geplanter Zeit, nur an Tagen mit Plan für
    die Art; eine Art braucht mindestens ``min_tage`` solche Tage. Blöcke gehören zum Tag ihres
    Starts (wie in der Tagesansicht); laufende Einträge fallen weg. Rückgabe je Art:
    {"art", "label", "faktor", "tage"} in der Reihenfolge von Kategorie.Art.
    """
    von = heute - timedelta(days=tage)
    summen = {}  # (datum, art) -> [geplant_min, erfasst_min]
    for index, quelle in enumerate((planbloecke, eintraege)):
        for block in quelle:
            datum = tagesdatum(block.start)
            if block.ende is None or not von <= datum < heute:
                continue
            je_art = summen.setdefault((datum, block.kategorie.art), [0.0, 0.0])
            je_art[index] += (block.ende - block.start).total_seconds() / 60
    verhaeltnisse = {}
    for (_, art), (geplant, erfasst) in summen.items():
        if geplant > 0:
            verhaeltnisse.setdefault(art, []).append(erfasst / geplant)
    return [
        {"art": art, "label": label, "faktor": median(v), "tage": len(v)}
        for art, label in Kategorie.Art.choices
        if len(v := verhaeltnisse.get(art, [])) >= min_tage
    ]


def realistische_minuten(geplant_min, faktor):
    """Geplante Dauer mal Plan-Faktor, auf ganze Minuten gerundet."""
    return round(geplant_min * faktor)
