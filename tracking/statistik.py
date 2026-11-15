"""Statistik-Bausteine für die Auswertung (docs/forschung.md, Abschnitt „Statistik“).

Reine Funktionen, nur Standardbibliothek. Zufall kommt immer über ein übergebenes
``random.Random``, damit Ergebnisse bei festem Seed reproduzierbar sind. Fehlende Werte (None)
werden paarweise entfernt. Wo etwas nicht berechenbar ist (zu wenig Werte, konstante Reihe),
kommt None zurück statt einer Ausnahme.
"""

import itertools
import math
import random
import statistics
from bisect import bisect_left, bisect_right
from operator import mul


def ohne_none(x, y):
    """Beide Reihen ohne die Positionen, an denen eine der beiden None ist."""
    paare = [(a, b) for a, b in zip(x, y, strict=True) if a is not None and b is not None]
    return [a for a, _ in paare], [b for _, b in paare]


def raenge(werte):
    """Ränge ab 1; gleiche Werte bekommen den mittleren Rang."""
    ordnung = sorted(range(len(werte)), key=werte.__getitem__)
    ergebnis = [0.0] * len(werte)
    i = 0
    while i < len(ordnung):
        j = i
        while j + 1 < len(ordnung) and werte[ordnung[j + 1]] == werte[ordnung[i]]:
            j += 1
        for k in range(i, j + 1):
            ergebnis[ordnung[k]] = (i + j) / 2 + 1
        i = j + 1
    return ergebnis


def pearson(x, y):
    """Pearson-r; None bei weniger als 3 Werten oder konstanter Reihe."""
    n = len(x)
    if n < 3:
        return None
    sx, sy = sum(x), sum(y)
    zaehler = n * sum(map(mul, x, y)) - sx * sy
    nenner = (n * sum(map(mul, x, x)) - sx * sx) * (n * sum(map(mul, y, y)) - sy * sy)
    return zaehler / nenner**0.5 if nenner > 1e-12 else None


def spearman(x, y):
    """Rangkorrelation (statistics.correlation, method="ranked"); None wenn nicht berechenbar."""
    x, y = ohne_none(x, y)
    if len(x) < 3:
        return None
    try:
        return statistics.correlation(x, y, method="ranked")
    except statistics.StatisticsError:  # konstante Reihe
        return None


def cliffs_delta(a, b):
    """Cliff's Delta in [-1, 1]: P(a > b) - P(a < b). Positiv = a liegt tendenziell höher."""
    a = [v for v in a if v is not None]
    b = sorted(v for v in b if v is not None)
    if not a or not b:
        return None
    # je a-Wert: Anzahl b darunter (bisect_left) bzw. darüber (n - bisect_right); O(n log n)
    mehr = sum(bisect_left(b, v) for v in a)
    weniger = sum(len(b) - bisect_right(b, v) for v in a)
    return (mehr - weniger) / (len(a) * len(b))


def block_bootstrap_ki(daten, statistik, blocklaenge=5, n=2000, rng=None, luecken_entfernen=True):
    """95-%-Perzentil-Intervall (unten, oben) per gleitendem Block-Bootstrap.

    ``daten`` ist eine Zeitreihe (Liste von Paaren oder Tagen in zeitlicher Reihenfolge).
    Es werden Blöcke von ``blocklaenge`` aufeinanderfolgenden Tagen gezogen, damit die
    Abhängigkeit benachbarter Tage erhalten bleibt (Autokorrelation). ``statistik`` bekommt die
    neu zusammengesetzte Liste und gibt eine Zahl oder None zurück. Mit ``luecken_entfernen``
    fallen None-Einträge und Paare mit None vorher weg. Ergebnis (None, None), wenn kaum
    Durchläufe ein Ergebnis liefern.
    """
    rng = rng or random.Random(0)
    if luecken_entfernen:
        daten = [d for d in daten if d is not None and not (isinstance(d, tuple) and None in d)]
    anzahl = len(daten)
    if anzahl < 2:
        return None, None
    laenge = min(blocklaenge, anzahl)
    bloecke = -(-anzahl // laenge)
    ergebnisse = []
    for _ in range(n):
        index = []
        for _ in range(bloecke):
            start = rng.randrange(anzahl - laenge + 1)
            index.extend(range(start, start + laenge))
        wert = statistik([daten[i] for i in index[:anzahl]])
        if wert is not None:
            ergebnisse.append(wert)
    if len(ergebnisse) < max(10, n // 2):
        return None, None
    ergebnisse.sort()
    m = len(ergebnisse)
    return ergebnisse[int(0.025 * m)], ergebnisse[min(m - 1, int(0.975 * m))]


def lag1(reihe):
    """Autokorrelation (Lag 1) über benachbarte Werte; Paare mit None fallen weg.

    Benachbart heißt hier: aufeinanderfolgend in der Liste, nicht zwingend am Folgetag.
    """
    x, y = ohne_none(reihe[:-1], reihe[1:])
    return pearson(x, y) if len(x) >= 5 else None


def effektives_n(n, r1):
    """Effektive Stichprobe bei Autokorrelation: n·(1−r1)/(1+r1), nur bei |r1| > 0,3.

    Negative Autokorrelation würde n künstlich vergrößern; das wird bei n gekappt.
    """
    if r1 is None or abs(r1) <= 0.3:
        return n
    return min(n, n * (1 - r1) / (1 + r1))


def wochentag_bereinigt(werte, wochentage):
    """Zieht je Wochentag den Mittelwert ab. None bleibt None.

    Wochentage mit weniger als 2 Werten bekommen None: ein Mittel aus einem Wert würde den Wert
    auf 0 setzen und dessen Information vernichten.
    """
    gruppen = {}
    for w, tag in zip(werte, wochentage, strict=True):
        if w is not None and tag is not None:
            gruppen.setdefault(tag, []).append(w)
    mittel = {tag: statistics.fmean(v) for tag, v in gruppen.items() if len(v) >= 2}
    return [
        w - mittel[tag] if w is not None and tag in mittel else None
        for w, tag in zip(werte, wochentage, strict=True)
    ]


def benjamini_hochberg(p_werte, q=0.1):
    """Benjamini-Hochberg: Liste bool (True = Treffer bei FDR q). None-p-Werte zählen nicht."""
    vorhanden = sorted((p, i) for i, p in enumerate(p_werte) if p is not None)
    m = len(vorhanden)
    grenze = 0
    for rang, (p, _) in enumerate(vorhanden, start=1):
        if p <= rang / m * q:
            grenze = rang
    treffer = [False] * len(p_werte)
    for _, i in vorhanden[:grenze]:
        treffer[i] = True
    return treffer


def permutation_p_korrelation(x, y, n=1000, rng=None):
    """Zweiseitiger Permutations-p-Wert der Spearman-Korrelation; None wenn nicht berechenbar.

    p = (Treffer + 1) / (n + 1), also nie 0. Gemischt wird y; Ränge und x bleiben fest, daher
    ändert sich nur die Summe der Rangprodukte.
    """
    rng = rng or random.Random(0)
    x, y = ohne_none(x, y)
    if len(x) < 3:
        return None
    rx, ry = raenge(x), raenge(y)
    beobachtet = pearson(rx, ry)
    if beobachtet is None:
        return None
    m = len(rx)
    sx, sy = sum(rx), sum(ry)
    nenner = ((m * sum(map(mul, rx, rx)) - sx * sx) * (m * sum(map(mul, ry, ry)) - sy * sy)) ** 0.5
    schwelle = abs(beobachtet) - 1e-9
    treffer = 0
    for _ in range(n):
        rng.shuffle(ry)
        r = (m * sum(map(mul, rx, ry)) - sx * sy) / nenner
        if abs(r) >= schwelle:
            treffer += 1
    return (treffer + 1) / (n + 1)


# --- Selbstexperimente: Randomisierungstest unter dem tatsächlichen Schema ------------------

MIN_JE_BEDINGUNG = 3  # Tage mit Wert je Bedingung, sonst keine Auswertung
MAX_EXAKT = 20_000  # bis zu so vielen zulässigen Zuweisungen wird exakt über alle gezählt


def median_differenz(werte, gruppen, mindestens=MIN_JE_BEDINGUNG):
    """Median(B) − Median(A); ``werte`` und ``gruppen`` ("A"/"B") sind gleich lang, None fällt weg.

    None, wenn eine Bedingung weniger als ``mindestens`` Werte hat.
    """
    a = [w for w, g in zip(werte, gruppen, strict=True) if g == "A" and w is not None]
    b = [w for w, g in zip(werte, gruppen, strict=True) if g == "B" and w is not None]
    if len(a) < mindestens or len(b) < mindestens:
        return None
    return statistics.median(b) - statistics.median(a)


def _einheiten(zuweisung, laenge):
    return [zuweisung[i] for i in range(0, len(zuweisung), laenge)]


def anzahl_zuweisungen(design, einheiten, k_b):
    """Zahl der nach dem Design zulässigen Zuweisungen (Einheiten = Tage bzw. Blöcke/Phasen)."""
    return 2 if design == "abab" else math.comb(einheiten, k_b)


def _zulaessige_einheiten(design, m, k_b):
    """Alle zulässigen Zuweisungen auf Einheiten-Ebene als Tupel aus "A"/"B"."""
    if design == "abab":
        yield from (("A", "B") * (m // 2), ("B", "A") * (m // 2))
        return
    for b_pos in itertools.combinations(range(m), k_b):
        gewaehlt = set(b_pos)
        yield tuple("B" if i in gewaehlt else "A" for i in range(m))


def _zufaellige_einheit(design, m, k_b, rng):
    if design == "abab":
        return ("A", "B") * (m // 2) if rng.random() < 0.5 else ("B", "A") * (m // 2)
    gewaehlt = set(rng.sample(range(m), k_b))
    return tuple("B" if i in gewaehlt else "A" for i in range(m))


def randomisierungstest(
    werte, zuweisung, design="tageweise", blocklaenge=1, n_perm=5000, rng=None, max_exakt=MAX_EXAKT
):
    """Randomisierungstest der Mediandifferenz B−A (Kratochwill & Levin 2010).

    Die Zuweisung wird so neu gezogen, wie sie ursprünglich gezogen wurde: tageweise = gleich
    viele B-Tage beliebig verteilt; Blöcke = ganze Blöcke von ``blocklaenge`` Tagen mit gleicher
    Zahl B-Blöcke; ABAB = nur ABAB oder BABA (4 Phasen à ``blocklaenge`` Tage). Gibt es höchstens
    ``max_exakt`` zulässige Zuweisungen, wird über alle gezählt (exakter p-Wert); sonst
    Monte-Carlo mit ``n_perm`` Ziehungen, p = (Treffer + 1) / (n_perm + 1). Zweiseitig.

    Rückgabe: dict mit beobachtet, p, exakt, n_zuweisungen und p_min (kleinster erreichbarer
    p-Wert dieses Schemas, 1/n_zuweisungen); None, wenn eine Bedingung zu wenige Werte hat.
    ABAB hat nur 2 Zuweisungen: der Test kann nie unter p = 0,5 kommen und bestätigt nichts.
    """
    rng = rng or random.Random(0)
    n = len(werte)
    if len(zuweisung) != n:
        raise ValueError("werte und zuweisung müssen gleich lang sein.")
    laenge = 1 if design == "tageweise" else blocklaenge
    einheiten = _einheiten(zuweisung, laenge)
    m, k_b = len(einheiten), einheiten.count("B")
    if design == "abab" and tuple(einheiten) not in (("A", "B") * (m // 2), ("B", "A") * (m // 2)):
        raise ValueError("Die Zuweisung ist kein ABAB-Muster.")
    beobachtet = median_differenz(werte, zuweisung)
    if beobachtet is None:
        return None
    gesamt = anzahl_zuweisungen(design, m, k_b)
    schwelle = abs(beobachtet) - 1e-9

    def trifft(einheit):
        tage = [e for e in einheit for _ in range(laenge)][:n]
        diff = median_differenz(werte, tage, mindestens=1)
        return diff is None or abs(diff) >= schwelle  # zu leere Gruppe: im Zweifel Treffer

    exakt = gesamt <= max_exakt
    if exakt:
        treffer = sum(trifft(e) for e in _zulaessige_einheiten(design, m, k_b))
        p, p_min = treffer / gesamt, 1 / gesamt
    else:
        treffer = sum(trifft(_zufaellige_einheit(design, m, k_b, rng)) for _ in range(n_perm))
        p, p_min = (treffer + 1) / (n_perm + 1), 1 / (n_perm + 1)
    return {
        "beobachtet": beobachtet,
        "p": p,
        "exakt": exakt,
        "n_zuweisungen": gesamt,
        "n_perm": None if exakt else n_perm,
        "p_min": p_min,
    }


def delta_mit_ki(b, a, n=1000, rng=None):
    """Cliff's Delta (B gegen A) und 95-%-Bootstrap-Intervall (je Bedingung neu gezogen).

    Rückgabe (delta, unten, oben); (None, None, None) ohne Werte. Die Tage innerhalb einer
    Bedingung gelten als austauschbar, weil die Bedingung zufällig zugewiesen wurde.
    """
    rng = rng or random.Random(0)
    b = [v for v in b if v is not None]
    a = [v for v in a if v is not None]
    delta = cliffs_delta(b, a)
    if delta is None:
        return None, None, None
    ergebnisse = sorted(
        cliffs_delta(rng.choices(b, k=len(b)), rng.choices(a, k=len(a))) for _ in range(n)
    )
    return delta, ergebnisse[int(0.025 * n)], ergebnisse[min(n - 1, int(0.975 * n))]
