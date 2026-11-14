import pytest

from tracking.auswertung import MIN_TAGE, vergleich


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
        keys, key=lambda k: -abs(next(z["effekt"] for z in r["zeilen"] if z["key"] == k))
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
