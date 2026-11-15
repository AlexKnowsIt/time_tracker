import random

import pytest

from tracking.auswertung import (
    MIN_TAGE,
    MIN_TAGE_KORRELATION,
    MIN_TAGE_MODELL,
    korrelationen,
    mehrfachmodell,
    vergleich,
)


def tag(prod, zufr=5, **merkmale):
    return {"produktivitaet": prod, "zufriedenheit": zufr}, merkmale


def test_min_tage():
    assert MIN_TAGE == 14


def test_drittel_mittelwerte_und_sortierung():
    # 9 Tage: Produktivität 1..9 -> schwach 1-3, gut 7-9
    tage = [
        tag(
            p,
            erste_pause=(12 * 60 if p <= 3 else 10 * 60),  # starker Unterschied
            pausen_anzahl=p % 3,  # kaum Unterschied
            wasser_ml=1000 + 100 * p,
        )
        for p in range(1, 10)
    ]
    r = vergleich(tage, "produktivitaet")
    assert (r["n"], r["gruppe_n"]) == (9, 3)
    assert r["ziel_gut"] == 8 and r["ziel_schwach"] == 2
    keys = [z["key"] for z in r["zeilen"]]
    assert set(keys) == {"erste_pause", "pausen_anzahl", "wasser_ml"}
    assert keys == sorted(
        keys, key=lambda k: -abs(next(z["delta"] for z in r["zeilen"] if z["key"] == k))
    )
    pause = next(z for z in r["zeilen"] if z["key"] == "erste_pause")
    assert (pause["gut"], pause["schwach"]) == (600, 720)
    assert pause["effekt"] < 0
    wasser = next(z for z in r["zeilen"] if z["key"] == "wasser_ml")
    assert wasser["gut"] == 1800 and wasser["schwach"] == 1200 and wasser["effekt"] > 0
    assert r["zeilen"][0]["format"] in {"uhrzeit", "ml", "zahl"}


def test_none_wird_ignoriert_und_merkmal_mit_zu_wenig_werten_entfaellt():
    # 12 Tage -> je 4 pro Gruppe; beim besten Tag fehlt das Wasser, bei allen außer einem die Pause
    tage = [
        tag(
            p,
            wasser_ml=None if p == 12 else (1000 if p > 8 else 500),
            erste_pause=600 if p == 12 else None,
        )
        for p in range(1, 13)
    ]
    r = vergleich(tage, "produktivitaet")
    wasser = next(z for z in r["zeilen"] if z["key"] == "wasser_ml")
    assert wasser["gut"] == 1000 and wasser["schwach"] == 500  # None ignoriert, 3 Werte reichen
    assert "erste_pause" not in {z["key"] for z in r["zeilen"]}  # nur ein Wert
    # nur 2 Werte in der guten Gruppe -> Merkmal entfällt
    tage = [tag(p, wasser_ml=None if p >= 11 else 700 + p) for p in range(1, 13)]
    assert vergleich(tage, "produktivitaet")["zeilen"] == []


def test_stdev_null_ergibt_effekt_null():
    r = vergleich([tag(p, pausen_anzahl=2) for p in range(1, 10)], "produktivitaet")
    assert r["zeilen"][0]["effekt"] == 0


def test_zielgroesse_umschalten():
    # Produktivität steigt, Zufriedenheit fällt mit dem Merkmal
    tage = [tag(p, 10 - p, pausen_anzahl=p) for p in range(1, 10)]
    prod = vergleich(tage, "produktivitaet")["zeilen"][0]
    zufr = vergleich(tage, "zufriedenheit")["zeilen"][0]
    assert prod["effekt"] > 0 > zufr["effekt"]
    assert vergleich(tage, "zufriedenheit")["ziel_gut"] == 8  # Zufriedenheit 7-9 = x 1-3


def test_zu_wenige_tage_ohne_zeilen():
    r = vergleich([tag(5, pausen_anzahl=1), tag(6, pausen_anzahl=2)], "produktivitaet")
    assert r["zeilen"] == [] and r["ziel_gut"] is None


@pytest.mark.parametrize("ziel", ["produktivitaet", "zufriedenheit"])
def test_unbekannte_merkmale_in_tagen_stoeren_nicht(ziel):
    assert vergleich([tag(p, 5, unbekannt=1) for p in range(1, 10)], ziel)["zeilen"] == []


# --- Phase 3a: Delta, Korrelationen, Mehrfachmodell -------------------------------


def reihe(n, merkmal, ziel_fn, seed=1):
    """n Tage in zeitlicher Reihenfolge; merkmal(i, rng) und ziel_fn(i, rng) liefern die Werte."""
    rng = random.Random(seed)
    tage = []
    for i in range(n):
        m = merkmal(i, rng)
        m["wochentag"] = i % 7
        tage.append(({"produktivitaet": ziel_fn(m, rng), "zufriedenheit": 5}, m))
    return tage


def test_vergleich_delta_und_deutlich():
    tage = reihe(
        45,
        lambda i, rng: {"pausen_anzahl": rng.gauss(0, 1), "wasser_ml": rng.gauss(0, 1)},
        lambda m, rng: round(5 + 2 * m["pausen_anzahl"] + rng.gauss(0, 0.3), 2),
    )
    r = vergleich(tage, "produktivitaet", random.Random(1), n_boot=200)
    erste = r["zeilen"][0]
    assert erste["key"] == "pausen_anzahl" and erste["delta"] > 0.8
    assert erste["deutlich"] and erste["ki_unten"] > 0
    zufall = next(z for z in r["zeilen"] if z["key"] == "wasser_ml")
    assert abs(zufall["delta"]) < abs(erste["delta"])
    assert zufall["ki_unten"] < zufall["delta"] < zufall["ki_oben"]
    assert [abs(z["delta"]) for z in r["zeilen"]] == sorted(
        (abs(z["delta"]) for z in r["zeilen"]), reverse=True
    )
    # deterministisch bei gleichem Seed
    assert vergleich(tage, "produktivitaet", random.Random(1), n_boot=200) == r


def test_korrelationen_erst_ab_30_tagen():
    tage = reihe(29, lambda i, rng: {"pausen_anzahl": rng.random()}, lambda m, rng: 5)
    assert korrelationen(tage, "produktivitaet")["zeilen"] == []
    assert MIN_TAGE_KORRELATION == 30 and MIN_TAGE_MODELL == 90


def test_korrelationen_hypothese_nur_ab_r_0_3_und_wochentag_bereinigt():
    def merkmal(i, rng):
        return {
            "pausen_anzahl": rng.gauss(0, 1),
            "wasser_ml": rng.gauss(0, 1),
            "kurze_bloecke": i % 7,
        }

    def ziel(m, rng):  # Wochentagseffekt im Ziel, der mit „nur_wochentag“ zusammenfällt
        return 5 + 1.5 * m["pausen_anzahl"] + 2 * (m["wochentag"] % 7) + rng.gauss(0, 0.5)

    tage = reihe(70, merkmal, ziel)
    k = korrelationen(tage, "produktivitaet", random.Random(2), n_boot=150, n_perm=200)
    zeilen = {z["key"]: z for z in k["zeilen"]}
    assert k["n"] == 70 and k["lag1"] is not None and k["n_eff"] == pytest.approx(70, rel=0.5)
    assert zeilen["pausen_anzahl"]["hypothese"] and zeilen["pausen_anzahl"]["r"] > 0.7
    assert (
        zeilen["pausen_anzahl"]["ki_unten"]
        < zeilen["pausen_anzahl"]["r"]
        < zeilen["pausen_anzahl"]["ki_oben"]
    )
    assert zeilen["pausen_anzahl"]["bh_treffer"] and zeilen["pausen_anzahl"]["p"] < 0.02
    assert not zeilen["wasser_ml"]["hypothese"] and abs(zeilen["wasser_ml"]["r"]) < 0.3
    # reiner Wochentagseffekt verschwindet nach der Bereinigung (konstant -> kein Eintrag)
    assert "kurze_bloecke" not in zeilen
    assert [abs(z["r"]) for z in k["zeilen"]] == sorted(
        (abs(z["r"]) for z in k["zeilen"]), reverse=True
    )


def test_korrelationen_ueberspringt_merkmale_mit_wenigen_paaren():
    tage = reihe(
        40,
        lambda i, rng: {
            "erste_pause": rng.random() if i < 10 else None,
            "anteil_nicht_erfasst": rng.random(),
        },
        lambda m, rng: rng.random(),
    )
    keys = {z["key"] for z in korrelationen(tage, "produktivitaet", random.Random(1))["zeilen"]}
    assert keys == {"anteil_nicht_erfasst"}


def test_mehrfachmodell_findet_den_treiber_und_laesst_lueckige_weg():
    def merkmal(i, rng):
        return {
            "deepwork_min": rng.gauss(0, 1),
            "wasser_ml": rng.gauss(0, 1),
            "laengster_deepwork_min": None,  # wird unten als Kopie von treiber gesetzt
            "erste_pause": rng.random() if i % 2 else None,  # 50 % Lücken: entfällt
            "pausen_min": 3,
        }

    tage = reihe(100, merkmal, lambda m, rng: 5 + 2 * m["deepwork_min"] + rng.gauss(0, 0.5))
    for _, m in tage:
        m["laengster_deepwork_min"] = (
            m["deepwork_min"] + 0.01
        )  # fast kollinear: Ridge darf nicht zusammenbrechen
    r = mehrfachmodell(tage, "produktivitaet")
    assert r["n"] == 100 and r["n_merkmale"] == 3  # lückig und konstant entfallen
    keys = [c["key"] for c in r["koeffizienten"]]
    assert set(keys[:2]) == {"deepwork_min", "laengster_deepwork_min"} and keys[2] == "wasser_ml"
    assert sum(c["koeff"] for c in r["koeffizienten"][:2]) == pytest.approx(0.97, abs=0.1)
    assert len(r["koeffizienten"]) <= 5


def test_mehrfachmodell_ab_90_tagen_und_median_fuellt_luecken():
    assert (
        mehrfachmodell(
            reihe(89, lambda i, rng: {"deepwork_min": rng.random()}, lambda m, r: 1),
            "produktivitaet",
        )["koeffizienten"]
        == []
    )
    tage = reihe(
        95,
        lambda i, rng: {
            "deepwork_min": rng.gauss(0, 1) if i % 10 else None
        },  # 10 % Lücken bleiben drin
        lambda m, rng: 5 + 2 * (m["deepwork_min"] or 0) + rng.gauss(0, 0.3),
    )
    r = mehrfachmodell(tage, "produktivitaet")
    assert r["n_merkmale"] == 1 and r["koeffizienten"][0]["koeff"] > 0.8


def test_loese_gauss_elimination():
    from tracking.auswertung import _loese

    # 2x + y = 5, x + 3y = 10 -> x = 1, y = 3; erste Zeile ohne Pivot (Zeilentausch nötig)
    assert _loese([[0.0, 1.0], [1.0, 0.0]], [3.0, 2.0]) == pytest.approx([2, 3])
    assert _loese([[2.0, 1.0], [1.0, 3.0]], [5.0, 10.0]) == pytest.approx([1, 3])
