import random
import statistics

import pytest

from tracking import statistik


def test_spearman_entspricht_statistics_und_ignoriert_none():
    x = [1, 2, 3, 4, 5, 6, 7, 8]
    y = [2, 1, 4, 3, 6, 8, 7, 5]
    assert statistik.spearman(x, y) == pytest.approx(statistics.correlation(x, y, method="ranked"))
    assert statistik.spearman(x + [None, 9], y + [3, None]) == pytest.approx(
        statistik.spearman(x, y)
    )


def test_spearman_monotone_nichtlinear_ist_eins_und_konstante_none():
    assert statistik.spearman([1, 2, 3, 4], [1, 4, 9, 100]) == pytest.approx(1)
    assert statistik.spearman([1, 2, 3, 4], [5, 5, 5, 5]) is None
    assert statistik.spearman([1, 2], [1, 2]) is None  # zu wenige Werte


def test_raenge_mit_gleichstand():
    assert statistik.raenge([10, 20, 20, 30]) == [1, 2.5, 2.5, 4]


def test_cliffs_delta_grenzfaelle():
    assert statistik.cliffs_delta([1, 2, 3], [1, 2, 3]) == 0
    assert statistik.cliffs_delta([4, 5, 6], [1, 2, 3]) == 1
    assert statistik.cliffs_delta([1, 2, 3], [4, 5, 6]) == -1
    assert statistik.cliffs_delta([1, 2, 3], []) is None
    # (2>1)=1 mehr; 2<3 und 4>1,4>3 -> a=[2,4], b=[1,3]: mehr=3, weniger=1 -> 2/4
    assert statistik.cliffs_delta([2, 4], [1, 3]) == pytest.approx(0.5)
    assert statistik.cliffs_delta([2, None, 4], [1, 3, None]) == pytest.approx(0.5)


def test_benjamini_hochberg_beispiel_aus_der_originalarbeit():
    # Benjamini & Hochberg 1995, 15 Hypothesen, q = 0,05: die ersten vier werden verworfen
    p = [
        0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344,
        0.0459, 0.3240, 0.4262, 0.5719, 0.6528, 0.7590, 1.000,
    ]  # fmt: skip
    assert statistik.benjamini_hochberg(p, q=0.05) == [True] * 4 + [False] * 11
    # Reihenfolge egal, None zählt nicht mit
    gemischt = [0.9, 0.001, None, 0.02]
    assert statistik.benjamini_hochberg(gemischt, q=0.1) == [False, True, False, True]
    assert statistik.benjamini_hochberg([]) == []


def test_lag1_und_effektives_n():
    reihe = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert statistik.lag1(reihe) == pytest.approx(1)
    assert statistik.lag1([1, -1] * 6) == pytest.approx(-1)
    assert statistik.lag1([1, 2, 3]) is None
    assert statistik.effektives_n(100, 0.5) == pytest.approx(100 * 0.5 / 1.5)
    assert statistik.effektives_n(100, 0.3) == 100  # nur bei |r1| > 0,3
    assert statistik.effektives_n(100, None) == 100
    assert statistik.effektives_n(100, -0.6) == 100  # negative Autokorrelation vergrößert nie


def test_wochentag_bereinigt():
    werte = [1, 3, 10, 14, None, 5]
    tage = [0, 0, 1, 1, 1, 2]
    # Montag Mittel 2, Dienstag Mittel 12 (aus 10 und 14), Mittwoch nur ein Wert -> None
    assert statistik.wochentag_bereinigt(werte, tage) == [-1, 1, -2, 2, None, None]


def test_block_bootstrap_deterministisch_und_plausibel():
    daten = [(i, 2 * i + random.Random(i).gauss(0, 1)) for i in range(60)]

    def steigung(paare):
        return statistik.spearman([a for a, _ in paare], [b for _, b in paare])

    a = statistik.block_bootstrap_ki(daten, steigung, 5, 200, random.Random(1))
    b = statistik.block_bootstrap_ki(daten, steigung, 5, 200, random.Random(1))
    assert a == b
    assert 0.9 < a[0] <= a[1] <= 1.0
    assert statistik.block_bootstrap_ki([(1, 1)], steigung, 5, 10, random.Random(1)) == (None, None)
    # Paare mit None fallen weg
    mit_luecken = daten + [(None, 3), (4, None)]
    assert statistik.block_bootstrap_ki(mit_luecken, steigung, 5, 200, random.Random(1)) == a


def test_permutation_p_stark_und_unabhaengig():
    rng = random.Random(3)
    x = list(range(40))
    stark = [v + rng.gauss(0, 3) for v in x]
    zufall = [rng.random() for _ in x]
    assert statistik.permutation_p_korrelation(x, stark, 300, random.Random(1)) == pytest.approx(
        1 / 301
    )
    assert statistik.permutation_p_korrelation(x, zufall, 300, random.Random(1)) > 0.05
    assert statistik.permutation_p_korrelation(x, [1] * 40, 100, random.Random(1)) is None
    assert statistik.permutation_p_korrelation([1, 2], [1, 2], 10, random.Random(1)) is None
    # Reproduzierbar bei gleichem Seed
    assert statistik.permutation_p_korrelation(
        x, zufall, 100, random.Random(5)
    ) == statistik.permutation_p_korrelation(x, zufall, 100, random.Random(5))
