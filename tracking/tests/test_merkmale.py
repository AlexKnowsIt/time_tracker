from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from tracking.merkmale import MERKMALE, formatiere, tagesmerkmale

BERLIN = ZoneInfo("Europe/Berlin")
TAG = date(2026, 11, 10)
JETZT = datetime(2026, 11, 10, 20, 0, tzinfo=BERLIN)

DEEP = SimpleNamespace(name="Deep Work", art="deepwork")
MAILS = SimpleNamespace(name="Mails", art="shallowwork")
MEET = SimpleNamespace(name="Meetings", art="shallowwork")
ORGA = SimpleNamespace(name="Organisation", art="organisation")
PAUSE = SimpleNamespace(name="Pause", art="pause")
SPORT = SimpleNamespace(name="Sport", art="freizeit")


def zeit(h, m=0, tag=TAG):
    return datetime(tag.year, tag.month, tag.day, h, m, tzinfo=BERLIN)


def e(kat, von, bis):
    """Eintrag von (h, m) bis (h, m); bis None = läuft."""
    return SimpleNamespace(kategorie=kat, start=zeit(*von), ende=zeit(*bis) if bis else None)


def wasser(h, menge=250):
    return SimpleNamespace(typ="wasser_ml", menge=menge, zeitpunkt=zeit(h))


def test_leerer_tag_alles_none():
    m = tagesmerkmale([], [], JETZT)
    assert all(v is None for v in m.values())
    assert {k for k, _, _ in MERKMALE} - {"schlaf_h", "produktivitaet_vortag"} <= set(m)


def test_beispieltag():
    eintraege = [
        e(DEEP, (8, 0), (9, 0)),
        e(DEEP, (9, 0), (9, 30)),  # schließt an -> ein Block von 90 min
        e(PAUSE, (9, 30), (9, 45)),
        e(MAILS, (9, 45), (9, 55)),  # kurz (10 min)
        e(DEEP, (10, 0), (10, 40)),  # 5 min Lücke davor, zweiter Block 40 min
        e(MEET, (10, 40), (11, 40)),
        e(SPORT, (12, 0), (12, 30)),
    ]
    m = tagesmerkmale(eintraege, [wasser(9), wasser(13, 500), wasser(15)], JETZT)
    assert m["deepwork_min"] == 130
    assert m["shallowwork_min"] == 70
    assert m["erfasst_min"] == 130 + 70 + 15 + 30
    assert m["anteil_nicht_erfasst"] == pytest.approx((270 - 245) / 270)  # 5 + 20 min Lücke
    assert m["beginn"] == 8 * 60 and m["ende"] == 11 * 60 + 40  # Freizeit zählt nicht
    assert m["deepwork_bloecke"] == 2
    assert m["laengster_deepwork_min"] == 90
    assert m["mittlerer_deepwork_min"] == 65
    assert m["kurze_bloecke"] == 1
    assert (m["pausen_anzahl"], m["pausen_min"], m["erste_pause"]) == (1, 15, 9 * 60 + 30)
    # nach der Pause: 10 + 40 + 60 = 110 min, davor 90 min
    assert m["laengste_strecke_ohne_pause_min"] == 110
    # Wechsel: Mails->(Lücke)Deep, Deep->Meetings; Deep->Pause und Pause->Mails zählen nicht
    assert m["wechsel_pro_h"] == pytest.approx(2 / (200 / 60))
    assert (m["wasser_ml"], m["wasser_bis_14_ml"]) == (1000, 750)
    assert m["wochentag"] == TAG.weekday()


def test_laufender_eintrag_zaehlt_bis_jetzt():
    m = tagesmerkmale([e(DEEP, (9, 0), None)], [], zeit(10, 30))
    assert m["deepwork_min"] == 90
    assert m["laengster_deepwork_min"] == 90
    assert m["anteil_nicht_erfasst"] == 0


def test_zusammenhaengende_bloecke_nur_ohne_luecke_und_ohne_anderes_dazwischen():
    eintraege = [
        e(DEEP, (8, 0), (8, 30)),
        e(DEEP, (8, 30), (9, 0)),
        e(DEEP, (9, 0), (9, 20)),
        e(MAILS, (9, 20), (9, 40)),
        e(DEEP, (9, 40), (10, 0)),
        e(DEEP, (10, 5), (10, 25)),  # Lücke -> neuer Block
    ]
    m = tagesmerkmale(eintraege, [], JETZT)
    assert m["deepwork_bloecke"] == 4 - 1  # 80 min | 20 min | 20 min
    assert m["laengster_deepwork_min"] == 80


def test_ohne_pause_und_ohne_wasser_sind_none():
    m = tagesmerkmale([e(DEEP, (8, 0), (9, 0)), e(ORGA, (9, 0), (9, 30))], [], JETZT)
    assert m["erste_pause"] is None and m["wasser_ml"] is None and m["wasser_bis_14_ml"] is None
    assert m["pausen_anzahl"] == 0 and m["pausen_min"] == 0
    assert m["laengste_strecke_ohne_pause_min"] == 90  # Organisation ist Arbeit


def test_nur_freizeit_und_pause_keine_arbeitsmerkmale():
    m = tagesmerkmale([e(SPORT, (8, 0), (9, 0)), e(PAUSE, (9, 0), (9, 15))], [], JETZT)
    assert m["beginn"] is None and m["wechsel_pro_h"] is None
    assert m["laengste_strecke_ohne_pause_min"] is None
    assert m["laengster_deepwork_min"] is None and m["deepwork_min"] == 0
    assert m["pausen_anzahl"] == 1


def test_ueberlappung_wird_nicht_doppelt_gezaehlt():
    m = tagesmerkmale([e(DEEP, (8, 0), (9, 0)), e(MAILS, (8, 30), (9, 30))], [], JETZT)
    assert m["deepwork_min"] == 60 and m["shallowwork_min"] == 30


def test_nur_wasser_ohne_eintraege():
    m = tagesmerkmale([], [wasser(9)], JETZT)
    assert m["wasser_ml"] == 250 and m["deepwork_min"] is None


def test_arbeit_ueber_mitternacht_gehoert_zum_tag_des_starts():
    start = (22, 0)
    eintrag = SimpleNamespace(
        kategorie=DEEP, start=zeit(*start), ende=zeit(1, 30, TAG + timedelta(days=1))
    )
    m = tagesmerkmale([eintrag], [], JETZT + timedelta(days=1))
    assert m["wochentag"] == TAG.weekday()
    assert m["beginn"] == 22 * 60 and m["ende"] == 25 * 60 + 30
    assert formatiere(m["ende"], "uhrzeit") == "01:30"


@pytest.mark.parametrize(
    ("wert", "format", "text"),
    [
        (None, "dauer", "–"),
        (95, "dauer", "1 h 35 min"),
        (40, "dauer", "40 min"),
        (10 * 60 + 40, "uhrzeit", "10:40"),
        (1560, "uhrzeit", "02:00"),
        (1234.4, "ml", "1234 ml"),
        (0.126, "prozent", "13 %"),
        (2.55, "zahl", "2,5"),
    ],
)
def test_formatiere(wert, format, text):
    assert formatiere(wert, format) == text
