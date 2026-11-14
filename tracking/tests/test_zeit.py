from datetime import date, datetime
from zoneinfo import ZoneInfo

from tracking.zeit import tagesdatum

BERLIN = ZoneInfo("Europe/Berlin")


def test_vor_vier_uhr_zaehlt_zum_vortag():
    assert tagesdatum(datetime(2026, 11, 14, 3, 59, tzinfo=BERLIN)) == date(2026, 11, 13)


def test_ab_vier_uhr_gleicher_tag():
    assert tagesdatum(datetime(2026, 11, 14, 4, 0, tzinfo=BERLIN)) == date(2026, 11, 14)


def test_utc_wird_lokal_umgerechnet():
    # 02:30 UTC im Sommer = 04:30 Berlin -> gleicher Tag; im Winter = 03:30 -> Vortag
    utc = ZoneInfo("UTC")
    assert tagesdatum(datetime(2026, 7, 10, 2, 30, tzinfo=utc)) == date(2026, 7, 10)
    assert tagesdatum(datetime(2026, 12, 10, 2, 30, tzinfo=utc)) == date(2026, 12, 9)


def test_sommerzeit_umstellung():
    # 29.03.2026: 02:00 -> 03:00. 03:30 lokal liegt vor 04:00, also Vortag.
    assert tagesdatum(datetime(2026, 3, 29, 3, 30, tzinfo=BERLIN)) == date(2026, 3, 28)
    assert tagesdatum(datetime(2026, 3, 29, 4, 0, tzinfo=BERLIN)) == date(2026, 3, 29)


def test_winterzeit_umstellung():
    # 25.10.2026: 03:00 -> 02:00, 02:30 kommt doppelt vor, beide Vortag.
    for fold in (0, 1):
        assert tagesdatum(datetime(2026, 10, 25, 2, 30, tzinfo=BERLIN, fold=fold)) == date(
            2026, 10, 24
        )
    assert tagesdatum(datetime(2026, 10, 25, 4, 0, tzinfo=BERLIN)) == date(2026, 10, 25)
