"""Stufen 2 bis 4 der Auswertung (Zielbild Abschnitt 6, docs/forschung.md). Reine Funktionen.

Beschreibt Unterschiede und Zusammenhänge zwischen Tagen, keine Ursachen. Alles ist
deterministisch: Zufall kommt über ein übergebenes ``random.Random``.
"""

import random
from statistics import StatisticsError, fmean, mean, median, pstdev, stdev

from . import statistik
from .merkmale import MERKMALE

MIN_TAGE = 14  # bewertete Tage bis zur ersten Auswertung (gute gegen schwache Tage)
MIN_TAGE_KORRELATION = 30
MIN_TAGE_MODELL = 90
MIN_WERTE = 3  # Werte je Gruppe, sonst fehlt das Merkmal
MIN_PAARE = 20  # Tage mit Wert und Score, sonst keine Korrelation für das Merkmal
HYPOTHESE_AB_R = 0.3
MAX_LUECKEN_MODELL = 0.3
RIDGE_LAMBDA = 1.0
BOOTSTRAP_BLOCK = 5
# Merkmale, die mit der Zielgröße zusammenfallen und deshalb nicht als „Muster“ taugen
AUSGESCHLOSSEN = {"schlaf_h": {"schlaf_h", "schlaf_schnitt_7", "schlafmitte"}}


def _delta_drittel(paare):
    """Cliff's Delta oberes gegen unteres Drittel nach Score; paare = [(score, wert|None)]."""
    paare = sorted(paare, key=lambda p: p[0])
    k = len(paare) // 3
    if k == 0:
        return None
    return statistik.cliffs_delta([w for _, w in paare[-k:]], [w for _, w in paare[:k]])


def vergleich(tage, zielgroesse, rng=None, n_boot=200):
    """tage: Liste von (bewertung_dict, merkmale_dict) in zeitlicher Reihenfolge.

    Oberes gegen unteres Drittel nach ``zielgroesse`` (z. B. "produktivitaet"). Je Merkmal: die
    Gruppenmittel, der Effekt (Differenz der Mittel durch die Streuung über alle Tage) und
    Cliff's Delta (gut gegen schwach) mit Block-Bootstrap-Intervall. „deutlich“ heißt: das
    Intervall schneidet die 0 nicht. Sortiert wird nach |Delta|.
    """
    rng = rng or random.Random(0)
    zeitreihe = list(tage)
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
        if key in AUSGESCHLOSSEN.get(zielgroesse, ()):
            continue
        w_gut, w_schwach = werte(gut, key), werte(schwach, key)
        if len(w_gut) < MIN_WERTE or len(w_schwach) < MIN_WERTE:
            continue
        streuung = stdev(werte(tage, key))
        mittel_gut, mittel_schwach = mean(w_gut), mean(w_schwach)
        reihe = [(b[zielgroesse], m.get(key)) for b, m in zeitreihe]
        unten, oben = statistik.block_bootstrap_ki(
            reihe, _delta_drittel, BOOTSTRAP_BLOCK, n_boot, rng, luecken_entfernen=False
        )
        ergebnis["zeilen"].append(
            {
                "key": key,
                "label": label,
                "format": format,
                "gut": mittel_gut,
                "schwach": mittel_schwach,
                "effekt": (mittel_gut - mittel_schwach) / streuung if streuung else 0,
                "delta": statistik.cliffs_delta(w_gut, w_schwach),
                "ki_unten": unten,
                "ki_oben": oben,
                "deutlich": unten is not None and (unten > 0 or oben < 0),
            }
        )
    ergebnis["zeilen"].sort(key=lambda z: abs(z["delta"] or 0), reverse=True)
    return ergebnis


def _bereinigt(tage, key, ziel):
    """(merkmal, ziel) je Tag, beide um den Wochentagsmittelwert bereinigt."""
    wochentage = [m.get("wochentag") for _, m in tage]
    x = statistik.wochentag_bereinigt([m.get(key) for _, m in tage], wochentage)
    y = statistik.wochentag_bereinigt([b[ziel] for b, _ in tage], wochentage)
    return x, y


def korrelationen(tage, zielgroesse, rng=None, n_boot=200, n_perm=400):
    """Spearman-Korrelation jedes Merkmals mit der Zielgröße, ab MIN_TAGE_KORRELATION Tagen.

    tage: (bewertung, merkmale) in zeitlicher Reihenfolge; merkmale["wochentag"] wird zum
    Bereinigen gebraucht. Je Merkmal: r, 95-%-Intervall (Block-Bootstrap über die Ränge),
    Permutations-p und der Benjamini-Hochberg-Treffer über alle Merkmale (q = 0,1). Als
    „Hypothese“ gilt nur |r| >= 0,3. Dazu Lag-1 der Zielgröße und die effektive Stichprobe.
    """
    rng = rng or random.Random(0)
    n = len(tage)
    ergebnis = {"n": n, "lag1": None, "n_eff": n, "zeilen": []}
    if n < MIN_TAGE_KORRELATION:
        return ergebnis
    ergebnis["lag1"] = statistik.lag1([b[zielgroesse] for b, _ in tage])
    ergebnis["n_eff"] = statistik.effektives_n(n, ergebnis["lag1"])
    zeilen = []
    for key, label, format in MERKMALE:
        if key in AUSGESCHLOSSEN.get(zielgroesse, ()):
            continue
        x, y = statistik.ohne_none(*_bereinigt(tage, key, zielgroesse))
        if len(x) < MIN_PAARE:
            continue
        r = statistik.spearman(x, y)
        if r is None:
            continue
        # Bootstrap über Ränge: zeitlich geordnete Rangpaare, Pearson darauf = Spearman
        rang_paare = list(zip(statistik.raenge(x), statistik.raenge(y), strict=True))
        unten, oben = statistik.block_bootstrap_ki(
            rang_paare,
            lambda p: statistik.pearson([a for a, _ in p], [b for _, b in p]),
            BOOTSTRAP_BLOCK,
            n_boot,
            rng,
        )
        zeilen.append(
            {
                "key": key,
                "label": label,
                "format": format,
                "n": len(x),
                "r": r,
                "ki_unten": unten,
                "ki_oben": oben,
                "p": statistik.permutation_p_korrelation(x, y, n_perm, rng),
                "hypothese": abs(r) >= HYPOTHESE_AB_R,
            }
        )
    treffer = statistik.benjamini_hochberg([z["p"] for z in zeilen])
    for z, t in zip(zeilen, treffer, strict=True):
        z["bh_treffer"] = t
    zeilen.sort(key=lambda z: abs(z["r"]), reverse=True)
    ergebnis["zeilen"] = zeilen
    return ergebnis


def _loese(a, b):
    """Löst a·x = b per Gauß-Elimination mit Spaltenpivot (a quadratisch, wird verändert)."""
    n = len(b)
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(a[r][i]))
        a[i], a[p], b[i], b[p] = a[p], a[i], b[p], b[i]
        for r in range(i + 1, n):
            f = a[r][i] / a[i][i]
            for c in range(i, n):
                a[r][c] -= f * a[i][c]
            b[r] -= f * b[i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (b[i] - sum(a[i][c] * x[c] for c in range(i + 1, n))) / a[i][i]
    return x


def mehrfachmodell(tage, zielgroesse, lam=RIDGE_LAMBDA):
    """Ridge-Regression der Zielgröße auf alle Merkmale zugleich, ab MIN_TAGE_MODELL Tagen.

    Merkmale mit mehr als 30 % Lücken (oder ohne Streuung) entfallen, übrige Lücken werden mit
    dem Median gefüllt. Standardisiert: ein Koeffizient ist die Änderung der Zielgröße in
    ihren Standardabweichungen je Standardabweichung des Merkmals, wenn die anderen Merkmale
    gleich bleiben. Rückgabe: die fünf betragsgrößten Koeffizienten.

    ponytail: kein Train/Test-Split und keine Intervalle, nur explorativ. Upgrade-Pfad:
    Kreuzvalidierung für lambda und Block-Bootstrap für die Koeffizienten.
    """
    n = len(tage)
    ergebnis = {"n": n, "n_merkmale": 0, "koeffizienten": []}
    if n < MIN_TAGE_MODELL:
        return ergebnis
    spalten = []
    for key, label, format in MERKMALE:
        if key in AUSGESCHLOSSEN.get(zielgroesse, ()):
            continue
        roh = [m.get(key) for _, m in tage]
        vorhanden = [w for w in roh if w is not None]
        if not vorhanden or (n - len(vorhanden)) / n > MAX_LUECKEN_MODELL:
            continue
        fuell = median(vorhanden)
        werte = [fuell if w is None else w for w in roh]
        mu, sigma = fmean(werte), pstdev(werte)
        if sigma == 0:
            continue
        spalten.append((key, label, format, [(w - mu) / sigma for w in werte]))
    ziel = [b[zielgroesse] for b, _ in tage]
    try:
        mu, sigma = fmean(ziel), pstdev(ziel)
    except StatisticsError:
        return ergebnis
    if not spalten or sigma == 0:
        return ergebnis
    y = [(w - mu) / sigma for w in ziel]
    z = [s[3] for s in spalten]
    p = len(z)
    gram = [
        [sum(a * b for a, b in zip(z[i], z[j], strict=True)) for j in range(p)] for i in range(p)
    ]
    for i in range(p):
        gram[i][i] += lam
    rechts = [sum(a * b for a, b in zip(z[i], y, strict=True)) for i in range(p)]
    beta = _loese(gram, rechts)
    ergebnis["n_merkmale"] = p
    ergebnis["koeffizienten"] = [
        {"key": s[0], "label": s[1], "format": s[2], "koeff": b}
        for s, b in sorted(zip(spalten, beta, strict=True), key=lambda t: abs(t[1]), reverse=True)[
            :5
        ]
    ]
    return ergebnis
