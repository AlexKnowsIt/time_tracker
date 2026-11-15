"""Tagesmerkmale (Zielbild Abschnitt 5): reine Funktionen ohne DB-Zugriff.

Eintrag-ähnliche Objekte: start, ende (None = läuft bis ``jetzt``), kategorie (art, Identität).
Messung-ähnliche Objekte: typ, menge, zeitpunkt. Fehlende Werte sind None.
Zeiten sind Minuten seit Mitternacht (lokale Wanduhr) des Tages, zu dem der Tag gehört. Arbeit
nach Mitternacht ergibt Werte über 1440; ``formatiere`` rechnet das für die Anzeige zurück.
"""

from django.utils import timezone

from .zeit import dauer_text, tagesdatum

KURZ_MIN = 15
WASSER_BIS_MIN = 14 * 60
WASSER_VOR_12_MIN, WASSER_BIS_16_MIN = 12 * 60, 16 * 60

DEEPWORK, SHALLOWWORK, PAUSE, FREIZEIT = "deepwork", "shallowwork", "pause", "freizeit"
ARBEIT = (DEEPWORK, SHALLOWWORK, "organisation")

# (Schlüssel, Label, Format); Format: dauer | uhrzeit | zahl | ml | prozent
# Die als _KONTEXT markierten kommen aus Bewertung und Vortagen (views.py), nicht aus
# tagesmerkmale(). Eintrag-ähnliche Objekte dürfen ``abgeschlossen``/``unterbrochen`` haben.
MERKMALE = [
    ("deepwork_min", "Deep Work gesamt", "dauer"),
    ("shallowwork_min", "Shallow Work gesamt", "dauer"),
    ("erfasst_min", "Erfasste Zeit", "dauer"),
    ("anteil_nicht_erfasst", "Anteil nicht erfasst", "prozent"),
    ("beginn", "Arbeitsbeginn", "uhrzeit"),
    ("ende", "Arbeitsende", "uhrzeit"),
    ("deepwork_bloecke", "Deep-Work-Blöcke", "zahl"),
    ("laengster_deepwork_min", "Längster Deep-Work-Block", "dauer"),
    ("mittlerer_deepwork_min", "Mittlerer Deep-Work-Block", "dauer"),
    ("wechsel_pro_h", "Kategoriewechsel pro Arbeitsstunde", "zahl"),
    ("kurze_bloecke", "Arbeitsblöcke unter 15 min", "zahl"),
    ("pausen_anzahl", "Pausen", "zahl"),
    ("pausen_min", "Pausenzeit", "dauer"),
    ("erste_pause", "Erste Pause", "uhrzeit"),
    ("laengste_strecke_ohne_pause_min", "Längste Strecke ohne Pause", "dauer"),
    ("wasser_ml", "Wasser gesamt", "ml"),
    ("wasser_bis_14_ml", "Wasser bis 14 Uhr", "ml"),
    ("pausen_je_deepwork_h", "Pausen je Deep-Work-Stunde", "zahl"),
    ("mittlere_pause_min", "Mittlere Pausenlänge", "dauer"),
    ("letzter_kaffee", "Letzter Kaffee", "uhrzeit"),
    ("wasser_vor_12_ml", "Wasser vor 12 Uhr", "ml"),
    ("wasser_12_16_ml", "Wasser 12 bis 16 Uhr", "ml"),
    ("anteil_unterbrochen", "Anteil unterbrochener Arbeitsblöcke", "prozent"),
    ("anteil_abgeschlossen", "Anteil abgeschlossener Arbeitsblöcke", "prozent"),
    ("anteil_nachgetragen", "Anteil nachgetragener Einträge", "prozent"),
    ("schlaf_h", "Schlaf (Stunden)", "zahl"),
    ("schlafmitte", "Schlafmitte", "uhrzeit"),
    ("letzter_kaffee_vortag", "Letzter Kaffee am Vortag", "uhrzeit"),
    ("schlaf_schnitt_7", "Schlaf-Schnitt der letzten 7 Nächte", "zahl"),
    ("produktivitaet_vortag", "Produktivität des Vortags", "zahl"),
    ("abgeschaltet_vortag", "Abschalten am Vortag (1–5)", "zahl"),
    ("fortschritt", "Tage mit Fortschritt", "prozent"),
]
_KONTEXT = {
    "schlaf_h",
    "schlafmitte",
    "letzter_kaffee_vortag",
    "schlaf_schnitt_7",
    "produktivitaet_vortag",
    "abgeschaltet_vortag",
    "fortschritt",
}
_SCHLUESSEL = [k for k, _, _ in MERKMALE if k not in _KONTEXT] + ["wochentag"]


def formatiere(wert, format):
    """Wert für die Anzeige; None wird zu „–“."""
    if wert is None:
        return "–"
    if format == "dauer":
        return dauer_text(wert * 60)
    if format == "uhrzeit":
        minuten = round(wert) % 1440
        return f"{minuten // 60:02d}:{minuten % 60:02d}"
    if format == "ml":
        return f"{round(wert)} ml"
    if format == "prozent":
        return f"{round(wert * 100)} %"
    return f"{wert:.1f}".replace(".", ",")


def minuten_seit_mitternacht(zeitpunkt, tag):
    """Lokale Wanduhr in Minuten seit Mitternacht des Tages ``tag`` (danach über 1440)."""
    z = timezone.localtime(zeitpunkt)
    return (z.date() - tag).days * 1440 + z.hour * 60 + z.minute + z.second / 60


def letzter_kaffee_min(messungen, tag):
    """Uhrzeit des letzten Kaffees des Tages ``tag`` in Minuten seit Mitternacht, sonst None."""
    zeiten = [minuten_seit_mitternacht(x.zeitpunkt, tag) for x in messungen if x.typ == "kaffee"]
    return max(zeiten) if zeiten else None


SCHLAF_MIN_H, SCHLAF_MAX_H = 0.5, 16  # darunter/darüber gilt Bett-/Aufstehzeit als Eingabefehler


def _schlaf_spanne(bettzeit, aufstehzeit):
    """(Bettzeit, Aufstehzeit) in Minuten relativ zur Mitternacht vor dem Aufstehen, sonst None.

    Eine Bettzeit ab 12 Uhr gehört zum Vorabend (negativ), davor zur Nacht danach.
    """
    if bettzeit is None or aufstehzeit is None:
        return None
    bett = bettzeit.hour * 60 + bettzeit.minute
    auf = aufstehzeit.hour * 60 + aufstehzeit.minute
    if bett >= 12 * 60:
        bett -= 1440
    dauer_h = (auf - bett) / 60
    return (bett, auf) if SCHLAF_MIN_H <= dauer_h <= SCHLAF_MAX_H else None


def schlafdauer_h(bettzeit, aufstehzeit):
    """Schlafdauer in Stunden (eine Nachkommastelle) oder None bei fehlender/unplausibler Zeit."""
    spanne = _schlaf_spanne(bettzeit, aufstehzeit)
    return round((spanne[1] - spanne[0]) / 60, 1) if spanne else None


def schlafmitte(bettzeit, aufstehzeit):
    """Mitte zwischen Bett- und Aufstehzeit in Minuten seit Mitternacht (z. B. 02:45 = 165)."""
    spanne = _schlaf_spanne(bettzeit, aufstehzeit)
    return (spanne[0] + spanne[1]) / 2 if spanne else None


SOZIAL_MIN_TAGE = 3  # je Gruppe (freie Tage, Werktage)


def sozialer_jetlag(nachtmitten):
    """Sozialer Jetlag in Minuten: Schlafmitte freier Tage minus Schlafmitte der Werktage.

    ``nachtmitten``: Paare (werktag: bool, schlafmitte_min). Werktag = Tag mit Arbeitseinträgen.
    Positiv = an freien Tagen später. None, wenn eine Gruppe unter SOZIAL_MIN_TAGE Tage hat.
    """
    werk = [m for w, m in nachtmitten if w and m is not None]
    frei = [m for w, m in nachtmitten if not w and m is not None]
    if len(werk) < SOZIAL_MIN_TAGE or len(frei) < SOZIAL_MIN_TAGE:
        return None
    return sum(frei) / len(frei) - sum(werk) / len(werk)


def tagesmerkmale(eintraege, messungen, jetzt):
    """Kennzahlen eines Tages. Überlappende Einträge werden nicht doppelt gezählt."""
    ergebnis = dict.fromkeys(_SCHLUESSEL)
    # Intervalle ohne Überlappung (Überstand wird abgeschnitten); leere fallen weg.
    teile, cursor = [], None
    for e in sorted(eintraege, key=lambda e: e.start):
        beginn = e.start if cursor is None else max(e.start, cursor)
        ende = e.ende or jetzt
        if ende > beginn:
            teile.append((beginn, ende, e.kategorie, e))
            cursor = ende

    zeitpunkte = [t[0] for t in teile] + [x.zeitpunkt for x in messungen]
    if not zeitpunkte:
        return ergebnis
    tag = tagesdatum(min(zeitpunkte))
    ergebnis["wochentag"] = tag.weekday()

    def minuten(z):
        return minuten_seit_mitternacht(z, tag)

    def dauer(t):
        return (t[1] - t[0]).total_seconds() / 60

    wasser = [x for x in messungen if x.typ == "wasser_ml"]
    if wasser:  # ponytail: ohne Messung None statt 0, vergessenes Erfassen ist nicht Durst
        ergebnis["wasser_ml"] = sum(x.menge for x in wasser)
        for key, von, bis in (
            ("wasser_bis_14_ml", 0, WASSER_BIS_MIN),
            ("wasser_vor_12_ml", 0, WASSER_VOR_12_MIN),
            ("wasser_12_16_ml", WASSER_VOR_12_MIN, WASSER_BIS_16_MIN),
        ):
            ergebnis[key] = sum(x.menge for x in wasser if von <= minuten(x.zeitpunkt) < bis)
    kaffee = [minuten(x.zeitpunkt) for x in messungen if x.typ == "kaffee"]
    if kaffee:
        ergebnis["letzter_kaffee"] = max(kaffee)
    if not teile:
        return ergebnis

    arbeit = [t for t in teile if t[2].art in ARBEIT]
    deep = [t for t in teile if t[2].art == DEEPWORK]
    pausen = [t for t in teile if t[2].art == PAUSE]
    spanne = (teile[-1][1] - teile[0][0]).total_seconds() / 60
    erfasst = sum(dauer(t) for t in teile)
    ergebnis.update(
        deepwork_min=sum(dauer(t) for t in deep),
        shallowwork_min=sum(dauer(t) for t in teile if t[2].art == SHALLOWWORK),
        erfasst_min=erfasst,
        anteil_nicht_erfasst=max(0.0, (spanne - erfasst) / spanne),
        kurze_bloecke=sum(1 for t in arbeit if dauer(t) < KURZ_MIN),
        pausen_anzahl=len(pausen),
        pausen_min=sum(dauer(t) for t in pausen),
        erste_pause=minuten(pausen[0][0]) if pausen else None,
        mittlere_pause_min=sum(dauer(t) for t in pausen) / len(pausen) if pausen else None,
    )

    ergebnis["anteil_nachgetragen"] = sum(
        1 for t in teile if getattr(t[3], "nachgetragen", False)
    ) / len(teile)

    if arbeit:
        ergebnis["beginn"] = minuten(arbeit[0][0])
        ergebnis["ende"] = minuten(arbeit[-1][1])
        stunden = sum(dauer(t) for t in arbeit) / 60
        # Wechsel nur zwischen unmittelbar aufeinanderfolgenden Arbeitseinträgen
        wechsel = sum(
            1
            for a, b in zip(teile, teile[1:], strict=False)
            if a[2].art in ARBEIT and b[2].art in ARBEIT and a[2] != b[2]
        )
        ergebnis["wechsel_pro_h"] = wechsel / stunden
        ergebnis["anteil_unterbrochen"] = sum(
            1 for t in arbeit if getattr(t[3], "unterbrochen", False)
        ) / len(arbeit)
        antworten = [
            t[3].abgeschlossen for t in arbeit if getattr(t[3], "abgeschlossen", None) is not None
        ]
        if antworten:
            ergebnis["anteil_abgeschlossen"] = sum(antworten) / len(antworten)
        # Eine Pause beendet die Strecke; Freizeit zählt weder dazu noch unterbricht sie.
        strecke = laengste = 0
        for t in teile:
            if t[2].art == PAUSE:
                strecke = 0
            elif t[2].art in ARBEIT:
                strecke += dauer(t)
                laengste = max(laengste, strecke)
        ergebnis["laengste_strecke_ohne_pause_min"] = laengste

    # Deep-Work-Block = unmittelbar aneinander anschließende Deep-Work-Einträge
    bloecke = []
    for t in deep:
        if bloecke and bloecke[-1][1] == t[0]:
            bloecke[-1][1] = t[1]
        else:
            bloecke.append([t[0], t[1]])
    laengen = [dauer(b) for b in bloecke]
    ergebnis["deepwork_bloecke"] = len(bloecke)
    deep_h = ergebnis["deepwork_min"] / 60
    if deep_h:
        ergebnis["pausen_je_deepwork_h"] = len(pausen) / deep_h
    if laengen:
        ergebnis["laengster_deepwork_min"] = max(laengen)
        ergebnis["mittlerer_deepwork_min"] = sum(laengen) / len(laengen)
    return ergebnis
