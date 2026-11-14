"""Stufe 2 (Zielbild Abschnitt 6): gute gegen schwache Tage. Reine Funktionen.

Beschreibt Unterschiede zwischen Tagen, keine Ursachen.
"""

from statistics import mean, stdev

from .merkmale import MERKMALE

MIN_TAGE = 14  # bewertete Tage bis zur ersten Auswertung
MIN_WERTE = 3  # Werte je Gruppe, sonst fehlt das Merkmal


def vergleich(tage, zielgroesse):
    """tage: Liste von (bewertung_dict, merkmale_dict). Oberes gegen unteres Drittel.

    ``zielgroesse`` ist ein Schlüssel der Bewertung (z. B. "produktivitaet"). Der Effekt ist die
    Differenz der Gruppenmittel geteilt durch die Standardabweichung über alle Tage, damit
    Merkmale in verschiedenen Einheiten vergleichbar sind.
    """
    tage = sorted(tage, key=lambda t: t[0][zielgroesse])
    k = len(tage) // 3
    ergebnis = {"n": len(tage), "gruppe_n": k, "ziel_gut": None, "ziel_schwach": None, "zeilen": []}
    if k == 0:
        return ergebnis
    schwach, gut = tage[:k], tage[-k:]
    ergebnis["ziel_gut"] = mean(b[zielgroesse] for b, _ in gut)
    ergebnis["ziel_schwach"] = mean(b[zielgroesse] for b, _ in schwach)

    def werte(gruppe, key):
        return [m[key] for _, m in gruppe if m.get(key) is not None]

    for key, label, format in MERKMALE:
        w_gut, w_schwach = werte(gut, key), werte(schwach, key)
        if len(w_gut) < MIN_WERTE or len(w_schwach) < MIN_WERTE:
            continue
        streuung = stdev(werte(tage, key))
        mittel_gut, mittel_schwach = mean(w_gut), mean(w_schwach)
        ergebnis["zeilen"].append(
            {
                "key": key,
                "label": label,
                "format": format,
                "gut": mittel_gut,
                "schwach": mittel_schwach,
                "effekt": (mittel_gut - mittel_schwach) / streuung if streuung else 0,
            }
        )
    ergebnis["zeilen"].sort(key=lambda z: abs(z["effekt"]), reverse=True)
    return ergebnis
