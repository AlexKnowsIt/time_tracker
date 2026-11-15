"""Phase 3b und Rest von Phase 5: Experimente, Plan-Faktor, nachgetragen, Schlafzeiten."""

import io
import json
import random
from datetime import date, datetime, time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from tracking import experimente, statistik
from tracking.merkmale import (
    letzter_kaffee_min,
    schlafdauer_h,
    schlafmitte,
    sozialer_jetlag,
    tagesmerkmale,
)
from tracking.models import (
    ApiToken,
    Eintrag,
    Experiment,
    ExperimentTag,
    Kategorie,
    Messung,
    Planblock,
    Tagesbewertung,
)
from tracking.plan import plan_faktor, realistische_minuten
from tracking.services import (
    beende_abgelaufene_experimente,
    bestaetige_experimenttag,
    breche_experiment_ab,
    lege_standardkategorien_an,
    starte_eintrag,
    starte_experiment,
)
from tracking.zeit import tagesdatum

pytestmark = pytest.mark.django_db


def lokal(tag, h, m=0):
    return timezone.make_aware(datetime.combine(tag, time(h, m)))


def heute():
    return tagesdatum(timezone.now())


@pytest.fixture
def nutzer():
    return get_user_model().objects.create_user("anna", password="geheim")


@pytest.fixture
def fremder():
    return get_user_model().objects.create_user("bernd", password="geheim")


@pytest.fixture
def client(client, nutzer):
    client.force_login(nutzer)
    return client


@pytest.fixture
def kat(nutzer):
    lege_standardkategorien_an(nutzer)
    return {k.name: k for k in Kategorie.objects.filter(nutzer=nutzer)}


def neues_experiment(nutzer, vorlage="mikropausen", start=None, **aendern):
    v = experimente.VORLAGEN[vorlage]
    felder = {
        "titel": v["titel"],
        "hypothese": v["hypothese"],
        "regel_wenn": v["wenn"],
        "regel_dann": v["dann"],
        "design": v["design"],
        "blocklaenge": v["blocklaenge"],
        "dauer_tage": v["dauer"],
        "zielgroesse": v["ziel"],
        "start": start or heute(),
        "seed": 7,
    }
    felder.update(aendern)
    return starte_experiment(nutzer, **felder)


# --- statistik.py: Randomisierungstest -------------------------------------------------


def _werte(zuweisung, a, b):
    return [b + (i % 3) * 0.1 if z == "B" else a + (i % 3) * 0.1 for i, z in enumerate(zuweisung)]


def test_zuweisung_tageweise_balanciert_und_reproduzierbar():
    for n in (20, 21):
        z = experimente.zuweisung("tageweise", n, 1, random.Random(3))
        assert len(z) == n and abs(z.count("A") - z.count("B")) == n % 2
    assert experimente.zuweisung("tageweise", 20, 1, random.Random(3)) == experimente.zuweisung(
        "tageweise", 20, 1, random.Random(3)
    )
    assert experimente.zuweisung("tageweise", 20, 1, random.Random(3)) != experimente.zuweisung(
        "tageweise", 20, 1, random.Random(4)
    )


def test_zuweisung_bloecke_und_abab():
    z = experimente.zuweisung("bloecke", 16, 2, random.Random(1))
    bloecke = [z[i : i + 2] for i in range(0, 16, 2)]
    assert all(b[0] == b[1] for b in bloecke)  # ganze Blöcke
    assert [b[0] for b in bloecke].count("B") == 4  # balanciert
    for seed in range(6):
        abab = experimente.zuweisung("abab", 28, 7, random.Random(seed))
        phasen = "".join(abab[i] for i in range(0, 28, 7))
        assert phasen in ("ABAB", "BABA")
        assert all(len(set(abab[i : i + 7])) == 1 for i in range(0, 28, 7))


@pytest.mark.parametrize(
    ("design", "dauer", "block"),
    [("tageweise", 5, 1), ("bloecke", 15, 2), ("bloecke", 6, 2), ("abab", 30, 7), ("abab", 28, 1)],
)
def test_ungueltiges_design_wird_abgelehnt(design, dauer, block):
    assert experimente.design_fehler(design, dauer, block)
    with pytest.raises(ValueError):
        experimente.zuweisung(design, dauer, block, random.Random(1))


def test_randomisierungstest_klarer_effekt_kleines_p():
    z = experimente.zuweisung("tageweise", 20, 1, random.Random(1))
    test = statistik.randomisierungstest(_werte(z, 3, 8), z, rng=random.Random(5))
    assert test["beobachtet"] == pytest.approx(5, abs=0.2)
    assert test["p"] < 0.05 and not test["exakt"]
    assert test["n_zuweisungen"] == 184756  # C(20, 10)


def test_randomisierungstest_kein_effekt_grosses_p():
    z = experimente.zuweisung("tageweise", 20, 1, random.Random(1))
    werte = [5 + (i * 7 % 4) for i in range(20)]  # Muster ohne Bezug zur Zuweisung
    test = statistik.randomisierungstest(werte, z, rng=random.Random(5))
    assert test["p"] > 0.3


def test_randomisierungstest_ist_deterministisch_per_seed():
    z = experimente.zuweisung("tageweise", 20, 1, random.Random(1))
    werte = [5 + (i * 7 % 4) + (1 if g == "B" else 0) for i, g in enumerate(z)]
    a = statistik.randomisierungstest(werte, z, rng=random.Random(9))
    b = statistik.randomisierungstest(werte, z, rng=random.Random(9))
    assert a == b


def test_randomisierungstest_bloecke_exakt():
    z = ["A", "A", "B", "B", "A", "A", "B", "B", "B", "B", "A", "A", "A", "A", "B", "B"]
    werte = _werte(z, 2, 9)
    test = statistik.randomisierungstest(werte, z, "bloecke", 2)
    assert test["exakt"] and test["n_zuweisungen"] == 70  # C(8, 4)
    assert test["p"] == pytest.approx(2 / 70)  # B-Blöcke vs. Spiegelbild
    assert test["p_min"] == pytest.approx(2 / 70)


def test_randomisierungstest_exakter_wert_bei_wenig_zuweisungen():
    z = ["A", "A", "B", "B", "A", "A", "B", "B"]  # 4 Blöcke à 2 Tage: C(4, 2) = 6
    test = statistik.randomisierungstest(_werte(z, 1, 9), z, "bloecke", 2)
    assert test["exakt"] and test["n_zuweisungen"] == 6
    assert test["p"] == pytest.approx(2 / 6)  # mehr als der Effekt geht bei 6 nicht


def test_randomisierungstest_abab_hat_nur_zwei_zuweisungen():
    z = experimente.zuweisung("abab", 28, 7, random.Random(2))
    test = statistik.randomisierungstest(_werte(z, 3, 8), z, "abab", 7)
    assert test["n_zuweisungen"] == 2 and test["exakt"] and test["p_min"] == 1.0
    erg = experimente.auswerten(
        [(g, w, None) for g, w in zip(z, _werte(z, 3, 8), strict=True)], "abab", 7, "produktivitaet"
    )
    assert erg["aussage"] == "nicht_pruefbar"
    assert "nichts bestätigen" in erg["text"] and "2 mögliche Zuweisungen" in erg["text"]
    with pytest.raises(ValueError):
        statistik.randomisierungstest(
            [1.0] * 28, ["A"] * 14 + ["B"] * 14, "abab", 7
        )  # AABB ist kein ABAB


def test_randomisierungstest_zu_wenige_werte():
    z = experimente.zuweisung("tageweise", 10, 1, random.Random(1))
    werte = [None] * 10
    assert statistik.randomisierungstest(werte, z) is None
    erg = experimente.auswerten([(g, None, None) for g in z], "tageweise", 1, "produktivitaet")
    assert erg["aussage"] == "zu_wenig" and "Keine Auswertung" in erg["text"]


def test_median_differenz_ignoriert_none():
    z = ["A", "A", "A", "B", "B", "B", "B"]
    assert statistik.median_differenz([1, 2, None, 5, 6, 7, None], z) is None  # A nur 2 Werte
    assert statistik.median_differenz([1, 2, 3, 5, 6, 7, None], z) == 4


def test_delta_mit_ki():
    delta, unten, oben = statistik.delta_mit_ki(
        [7, 8, 9, 8, 7, 9], [2, 3, 4, 3, 2, 4], rng=random.Random(1)
    )
    assert delta == 1.0 and unten == 1.0 and oben == 1.0
    delta, unten, oben = statistik.delta_mit_ki([1, 2, 3, 4], [2, 3, 1, 4], rng=random.Random(1))
    assert unten < 0 < oben
    assert statistik.delta_mit_ki([], [1])[0] is None


def test_auswerten_intention_to_treat_und_nebenergebnis():
    z = experimente.zuweisung("tageweise", 20, 1, random.Random(1))
    werte = _werte(z, 3, 8)
    # an drei B-Tagen nicht eingehalten (Wert wie A): ITT zählt sie weiter zu B
    tage, schlecht = [], 0
    for g, w in zip(z, werte, strict=True):
        if g == "B" and schlecht < 3:
            schlecht += 1
            tage.append((g, 3.0, False))
        else:
            tage.append((g, w, True if g == "B" else None))
    erg = experimente.auswerten(tage, "tageweise", 1, "zufriedenheit", random.Random(1))
    assert erg["n_b"] == 10 and erg["n_a"] == 10  # ITT: alle zugewiesenen Tage
    assert erg["protokoll"]["n_b"] == 7 and erg["protokoll"]["n_a"] == 10
    assert erg["protokoll"]["differenz"] > erg["differenz"]  # ohne die Ausreißer größer
    assert erg["einhaltung_b"] == pytest.approx(0.7) and erg["einhaltung_b_n"] == 10
    assert erg["aussage"] in ("dafuer", "hinweis")
    text = erg["text"].lower()
    assert "verursach" not in text and "bewirk" not in text and "beweist" not in text


def test_ergebnis_text_ohne_unterschied_ist_vorsichtig():
    z = experimente.zuweisung("tageweise", 20, 1, random.Random(1))
    werte = [5 + (i * 7 % 4) for i in range(20)]
    erg = experimente.auswerten(
        [(g, w, None) for g, w in zip(z, werte, strict=True)], "tageweise", 1, "produktivitaet"
    )
    assert erg["aussage"] == "unklar" and "Kein klarer Unterschied" in erg["text"]


def test_alle_vorlagen_sind_gueltig():
    assert len(experimente.VORLAGEN) == 8
    for key, v in experimente.VORLAGEN.items():
        assert v["ziel"] in experimente.ZIELE, key
        assert not experimente.design_fehler(v["design"], v["dauer"], v["blocklaenge"]), key
        assert v["hinweis"] and v["wenn"] and v["dann"]


# --- Modell und Services ---------------------------------------------------------------


def test_start_erzeugt_balancierte_unveraenderliche_zuweisung(nutzer):
    e = neues_experiment(nutzer)
    tage = list(e.tage.all())
    assert [t.datum for t in tage] == [e.start + timedelta(days=i) for i in range(20)]
    assert sum(t.bedingung == "B" for t in tage) == 10
    assert [t.bedingung for t in tage] == experimente.zuweisung(
        "tageweise", 20, 1, random.Random(7)
    )  # aus dem Seed reproduzierbar
    tag = tage[0]
    tag.bedingung = "A" if tag.bedingung == "B" else "B"
    with pytest.raises(ValueError, match="unveränderlich"):
        tag.save()
    tag = ExperimentTag.objects.get(pk=tag.pk)
    tag.datum += timedelta(days=100)
    with pytest.raises(ValueError):
        tag.save()
    tag = ExperimentTag.objects.get(pk=tag.pk)
    tag.eingehalten = True  # nur das darf sich ändern
    tag.save()


def test_gestartetes_experiment_ist_schreibgeschuetzt(nutzer):
    e = neues_experiment(nutzer)
    assert e.regel_satz == "Wenn ich 50 Minuten gearbeitet habe, dann mache ich 5–10 Minuten Pause."
    for feld, wert in (
        ("hypothese", "ganz anders"),
        ("zielgroesse", "produktivitaet"),
        ("dauer_tage", 10),
        ("regel_dann", "egal"),
    ):
        e = Experiment.objects.get(pk=e.pk)
        setattr(e, feld, wert)
        with pytest.raises(ValueError, match="nicht mehr ändern"):
            e.save()


def test_nur_ein_laufendes_experiment(nutzer, fremder):
    neues_experiment(nutzer)
    with pytest.raises(ValueError, match="läuft schon"):
        neues_experiment(nutzer, "abschlussnotiz")
    neues_experiment(fremder)  # anderer Nutzer: kein Konflikt
    assert Experiment.objects.filter(status="laeuft").count() == 2
    assert Experiment.objects.filter(nutzer=nutzer).count() == 1  # nichts Halbes angelegt
    assert not ExperimentTag.objects.filter(experiment__titel="Abschlussnotiz").exists()
    with pytest.raises(IntegrityError):  # auch die Datenbank erzwingt es
        Experiment.objects.create(
            nutzer=nutzer, titel="x", hypothese="x", regel_wenn="a", regel_dann="b",
            design="tageweise", zielgroesse="produktivitaet", start=heute(), dauer_tage=10, seed=1,
        )  # fmt: skip


def test_abbruch_nur_mit_vermerk(nutzer):
    e = neues_experiment(nutzer)
    for leer in ("", "   ", None):
        with pytest.raises(ValueError, match="Vermerk"):
            breche_experiment_ab(e, leer)
    breche_experiment_ab(e, "Zu stressig")
    e.refresh_from_db()
    assert e.status == "abgebrochen" and e.abbruch_vermerk == "Zu stressig"
    neues_experiment(nutzer, "abschlussnotiz")  # danach darf ein neues laufen


def test_abgelaufenes_experiment_wird_beendet(nutzer):
    e = neues_experiment(nutzer, start=heute() - timedelta(days=30))
    laufend = neues_experiment(
        neu := get_user_model().objects.create_user("clara"), start=heute() - timedelta(days=3)
    )
    beende_abgelaufene_experimente(nutzer, heute())
    beende_abgelaufene_experimente(neu, heute())
    e.refresh_from_db()
    laufend.refresh_from_db()
    assert e.status == "beendet" and laufend.status == "laeuft"


def test_bestaetige_tag_nur_eigene_und_nicht_abgebrochene(nutzer, fremder):
    e = neues_experiment(nutzer)
    assert bestaetige_experimenttag(nutzer, heute(), True).eingehalten is True
    assert bestaetige_experimenttag(fremder, heute(), True) is None
    assert bestaetige_experimenttag(nutzer, heute() - timedelta(days=5), True) is None
    breche_experiment_ab(e, "weg")
    assert bestaetige_experimenttag(nutzer, heute(), False) is None


# --- Seiten: Experimente ---------------------------------------------------------------


def test_experiment_seiten_brauchen_login(client):
    client.logout()
    for name, args in (("experimente", []), ("experiment_neu", []), ("experiment_detail", [1])):
        assert client.get(reverse(name, args=args)).status_code == 302


def test_experimente_liste_zeigt_vorlagen_und_beendete(client, nutzer):
    html = client.get(reverse("experimente")).content.decode()
    for v in experimente.VORLAGEN.values():
        assert v["titel"] in html
    assert "Noch kein Experiment beendet" in html
    assert "Wenn ich 50 Minuten gearbeitet habe, dann mache ich 5–10 Minuten Pause." in html
    assert "Drake et al. 2013" in html


def test_experiment_anlegen_per_vorlage_prg_und_nur_eines(client, nutzer):
    antwort = client.get(reverse("experiment_neu") + "?vorlage=koffein_schluss")
    assert antwort.context["form"].initial["regel_dann"] == "trinke ich keinen Kaffee mehr"
    assert f'value="{heute()}"' in antwort.content.decode()  # type=date braucht ISO
    daten = {
        "titel": "Koffein-Schluss",
        "hypothese": "Besser schlafen",
        "regel_wenn": "Wenn es 14 Uhr ist",  # „Wenn“ doppelt: wird bereinigt
        "regel_dann": "trinke ich keinen Kaffee mehr.",
        "bedingung_a": "Wie immer",
        "design": "bloecke",
        "blocklaenge": 2,
        "dauer_tage": 16,
        "zielgroesse": "schlaf_folgenacht",
        "start": str(heute()),
    }
    antwort = client.post(reverse("experiment_neu"), daten)
    assert antwort.status_code == 302 and antwort.url == reverse("experimente")  # PRG
    e = Experiment.objects.get(nutzer=nutzer)
    assert e.regel_satz == "Wenn es 14 Uhr ist, dann trinke ich keinen Kaffee mehr."
    assert e.tage.count() == 16 and e.status == "laeuft"
    zweites = client.post(reverse("experiment_neu"), daten)
    assert zweites.status_code == 200 and "läuft schon ein Experiment" in zweites.content.decode()
    assert Experiment.objects.count() == 1


@pytest.mark.parametrize(
    "aenderung",
    [
        {"regel_wenn": ""},
        {"regel_dann": "ab"},
        {"design": "bloecke", "blocklaenge": 3, "dauer_tage": 16},
        {"design": "tageweise", "dauer_tage": 4},
        {"zielgroesse": "wasser"},
        {"start": str(date(2000, 1, 1))},
    ],
)
def test_experiment_formular_validiert(client, nutzer, aenderung):
    daten = {
        "titel": "T",
        "hypothese": "H",
        "regel_wenn": "es regnet",
        "regel_dann": "bleibe ich drin",
        "bedingung_a": "Wie immer",
        "design": "tageweise",
        "blocklaenge": 1,
        "dauer_tage": 20,
        "zielgroesse": "zufriedenheit",
        "start": str(heute()),
    }
    daten.update(aenderung)
    assert client.post(reverse("experiment_neu"), daten).status_code == 200
    assert not Experiment.objects.exists()


def test_abab_dauer_ergibt_sich_aus_phasenlaenge(client, nutzer):
    daten = {
        "titel": "T",
        "hypothese": "H",
        "regel_wenn": "es regnet",
        "regel_dann": "bleibe ich drin",
        "bedingung_a": "Wie immer",
        "design": "abab",
        "blocklaenge": 7,
        "dauer_tage": "",
        "zielgroesse": "zufriedenheit",
        "start": str(heute()),
    }
    assert client.post(reverse("experiment_neu"), daten).status_code == 302
    assert Experiment.objects.get().dauer_tage == 28


def test_fremdes_experiment_404(client, fremder):
    e = neues_experiment(fremder)
    assert client.get(reverse("experiment_detail", args=[e.pk])).status_code == 404
    antwort = client.post(reverse("experiment_abbrechen", args=[e.pk]), {"vermerk": "x"})
    assert antwort.status_code == 404
    e.refresh_from_db()
    assert e.status == "laeuft"


def test_abbrechen_braucht_vermerk_und_post(client, nutzer):
    e = neues_experiment(nutzer)
    url = reverse("experiment_abbrechen", args=[e.pk])
    assert client.get(url).status_code == 405
    assert client.post(url, {"vermerk": "  "}).status_code == 200
    e.refresh_from_db()
    assert e.status == "laeuft"
    antwort = client.post(url, {"vermerk": "Urlaub dazwischen"})
    assert antwort.status_code == 302
    e.refresh_from_db()
    assert e.status == "abgebrochen"
    html = client.get(reverse("experiment_detail", args=[e.pk])).content.decode()
    assert "Urlaub dazwischen" in html


def test_laufendes_experiment_zeigt_kein_ergebnis(client, nutzer):
    e = neues_experiment(nutzer)
    html = client.get(reverse("experiment_detail", args=[e.pk])).content.decode()
    assert "erscheint erst nach dem Ende" in html and "Randomisierungstest" not in html
    assert "Experiment abbrechen" in html


def bewerte(nutzer, tag, produktiv=6, zufrieden=6, **extra):
    return Tagesbewertung.objects.create(
        nutzer=nutzer, datum=tag, produktivitaet=produktiv, zufriedenheit=zufrieden, **extra
    )


def beendetes_experiment(nutzer, effekt=3, vorlage="mikropausen"):
    """Experiment in der Vergangenheit mit Bewertungen (B-Tage um ``effekt`` höher)."""
    start = heute() - timedelta(days=30)
    e = neues_experiment(nutzer, vorlage, start=start)
    for i, t in enumerate(e.tage.all()):
        bewerte(nutzer, t.datum, 5, 4 + (i % 3) + (effekt if t.bedingung == "B" else 0))
    beende_abgelaufene_experimente(nutzer, heute())
    return e


def test_beendetes_experiment_ergebnis_in_liste_und_detail(client, nutzer):
    e = beendetes_experiment(nutzer)
    html = client.get(reverse("experimente")).content.decode()
    assert "Spricht dafür" in html and "Mikropausen" in html
    detail = client.get(reverse("experiment_detail", args=[e.pk])).content.decode()
    assert "Randomisierungstest" in detail and "Cliff" in detail
    assert "Nebenergebnis" not in detail  # niemand hat „nicht eingehalten“ gemeldet
    assert "Zuweisung der Tage" in detail and "Median B minus A: +3,5" in detail


def test_liste_ohne_n_plus_1(client, nutzer, django_assert_max_num_queries):
    beendetes_experiment(nutzer)
    start = heute() - timedelta(days=60)
    for vorlage in ("abschlussnotiz", "gebuendelte_kommunikation", "wenn_dann_start"):
        e = neues_experiment(nutzer, vorlage, start=start)
        e.status = "beendet"
        e.save(update_fields=["status"])
        start -= timedelta(days=40)
    with django_assert_max_num_queries(14):
        assert client.get(reverse("experimente")).status_code == 200


def test_jetzt_banner_und_abschlussfrage(client, nutzer, kat):
    html = client.get(reverse("jetzt")).content.decode()
    assert "Heute im Experiment" not in html
    e = neues_experiment(nutzer)
    tag = e.tage.get(datum=heute())
    html = client.get(reverse("jetzt")).content.decode()
    assert "Heute im Experiment" in html and f"Bedingung {tag.bedingung}" in html
    if tag.bedingung == "B":
        assert "Wenn ich 50 Minuten gearbeitet habe" in html
    seite = client.get(reverse("abschluss", args=[heute()])).content.decode()
    assert "Hast du dich heute an die Bedingung gehalten?" in seite
    daten = {"produktivitaet": 6, "zufriedenheit": 7, "fortschritt": "True", "eingehalten": "False"}
    assert client.post(reverse("abschluss", args=[heute()]), daten).status_code == 302
    tag.refresh_from_db()
    assert tag.eingehalten is False


def test_abschluss_ohne_experimenttag_hat_keine_frage(client, nutzer):
    seite = client.get(reverse("abschluss", args=[heute()])).content.decode()
    assert "an die Bedingung gehalten" not in seite
    neues_experiment(nutzer, start=heute() + timedelta(days=3))
    seite = client.get(reverse("abschluss", args=[heute()])).content.decode()
    assert "an die Bedingung gehalten" not in seite  # heute kein Experimenttag


def test_experiment_fremder_nutzer_erscheint_nicht_auf_jetzt(client, fremder):
    neues_experiment(fremder)
    assert "Heute im Experiment" not in client.get(reverse("jetzt")).content.decode()


def test_muster_verweist_auf_experimente_und_kuerzt_badge(client, nutzer):
    html = client.get(reverse("muster")).content.decode()
    assert reverse("experimente") in html and "Eine Hypothese prüfen" in html
    neues_experiment(nutzer)
    assert "Experiment läuft" in client.get(reverse("muster")).content.decode()
    assert "bleibt nach Mehrfachtest-Korrektur" not in html


def test_navigation_experimente_nur_in_seitenleiste_vorhanden(client):
    html = client.get(reverse("jetzt")).content.decode()
    assert 'class="nur-seitenleiste"' in html and reverse("experimente") in html


# --- Experiment-Werte je Zielgröße -----------------------------------------------------


def test_werte_schlaf_folgenacht_und_plan_erfuellung(nutzer, kat):
    from tracking.experiment_views import experiment_werte

    e = neues_experiment(nutzer, "koffein_schluss", start=heute() - timedelta(days=10))
    d0 = e.start
    bewerte(nutzer, d0 + timedelta(days=1), schlaf_h=6.5)
    ew = experiment_werte(
        nutzer, [Experiment.objects.prefetch_related("tage").get(pk=e.pk)], timezone.now()
    )
    assert ew[e.pk][d0] == 6.5 and ew[e.pk][d0 + timedelta(days=1)] is None

    e.status = "beendet"
    e.save(update_fields=["status"])
    p = neues_experiment(nutzer, "plan_puffer", start=heute() - timedelta(days=40))
    tag = p.start
    bewerte(nutzer, tag)
    Planblock.objects.create(
        nutzer=nutzer, kategorie=kat["Deep Work"], start=lokal(tag, 9), ende=lokal(tag, 11)
    )
    Eintrag.objects.create(
        nutzer=nutzer, kategorie=kat["Deep Work"], start=lokal(tag, 9), ende=lokal(tag, 10, 30)
    )
    ew = experiment_werte(
        nutzer, [Experiment.objects.prefetch_related("tage").get(pk=p.pk)], timezone.now()
    )
    assert ew[p.pk][tag] == pytest.approx(0.75)
    assert ew[p.pk][tag + timedelta(days=1)] is None  # kein Plan, keine Bewertung


# --- Plan-Faktor -----------------------------------------------------------------------


class Block:
    def __init__(self, art, start, ende):
        self.kategorie = type("K", (), {"art": art})()
        self.start, self.ende = start, ende


def test_plan_faktor_median_je_art_mit_mindesttagen():
    h = date(2026, 11, 15)
    plan, ist = [], []
    for i in range(1, 8):  # 7 Tage Deep Work: Verhältnisse 0,5 .. 0,8
        tag = h - timedelta(days=i)
        plan.append(Block("deepwork", lokal(tag, 9), lokal(tag, 11)))  # 120 min
        ist.append(Block("deepwork", lokal(tag, 9), lokal(tag, 9) + timedelta(minutes=60 + 5 * i)))
    for i in range(1, 5):  # nur 4 Tage Shallow Work: zu wenig
        tag = h - timedelta(days=i)
        plan.append(Block("shallowwork", lokal(tag, 12), lokal(tag, 13)))
        ist.append(Block("shallowwork", lokal(tag, 12), lokal(tag, 13)))
    ergebnis = plan_faktor(plan, ist, h)
    assert [e["art"] for e in ergebnis] == ["deepwork"]
    assert ergebnis[0]["faktor"] == pytest.approx(80 / 120) and ergebnis[0]["tage"] == 7
    assert realistische_minuten(180, ergebnis[0]["faktor"]) == 120


def test_plan_faktor_fenster_heute_und_laufende_zaehlen_nicht():
    h = date(2026, 11, 15)
    plan, ist = [], []
    for i in (0, 29, 30):  # heute und älter als 28 Tage
        tag = h - timedelta(days=i)
        plan.append(Block("deepwork", lokal(tag, 9), lokal(tag, 11)))
        ist.append(Block("deepwork", lokal(tag, 9), lokal(tag, 10)))
    assert plan_faktor(plan, ist, h, min_tage=1) == []
    tag = h - timedelta(days=1)
    plan = [Block("deepwork", lokal(tag, 9), lokal(tag, 11))]
    assert (
        plan_faktor(plan, [Block("deepwork", lokal(tag, 9), None)], h, min_tage=1)[0]["faktor"] == 0
    )  # laufender Eintrag zählt nicht, Plan ohne Ist = 0 %
    assert plan_faktor([], [Block("deepwork", lokal(tag, 9), lokal(tag, 10))], h, min_tage=1) == []


def test_plan_seite_zeigt_faktor_und_dialog_hinweis(client, nutzer, kat):
    for i in range(1, 8):
        tag = heute() - timedelta(days=i)
        Planblock.objects.create(
            nutzer=nutzer, kategorie=kat["Deep Work"], start=lokal(tag, 9), ende=lokal(tag, 11)
        )
        Eintrag.objects.create(
            nutzer=nutzer, kategorie=kat["Deep Work"], start=lokal(tag, 9), ende=lokal(tag, 10, 24)
        )
    html = client.get(reverse("plan")).content.decode()
    assert "Deep Work: du schaffst im Median <strong>70 %</strong> des Plans" in html
    assert 'data-art="deepwork"' in html and 'id="plan-faktoren"' in html
    assert 'id="plan-realistisch"' in html


def test_plan_faktor_ohne_daten_kein_block(client):
    html = client.get(reverse("plan")).content.decode()
    assert "Plan-Faktor" not in html


# --- nachgetragen ----------------------------------------------------------------------


def test_nachgetragen_timer_formular_api(client, nutzer, kat):
    timer = starte_eintrag(nutzer, kat["Mails"])
    assert timer.nachgetragen is False
    tag = heute() - timedelta(days=1)
    daten = {
        "kategorie": kat["Deep Work"].pk,
        "start": f"{tag}T09:00",
        "ende": f"{tag}T10:00",
        "notiz": "",
    }
    assert client.post(reverse("eintrag_neu", args=[tag]), daten).status_code == 302
    formular = Eintrag.objects.get(kategorie=kat["Deep Work"])
    assert formular.nachgetragen is True
    # Bearbeiten ändert das Kennzeichen nicht
    timer.ende = timer.start + timedelta(minutes=5)
    timer.save()
    daten.update(kategorie=kat["Mails"].pk, start=f"{tag}T11:00", ende=f"{tag}T12:00")
    client.post(reverse("eintrag_bearbeiten", args=[timer.pk]), daten)
    timer.refresh_from_db()
    assert timer.nachgetragen is False

    token = ApiToken.erzeugen(nutzer, "t")[1]
    antwort = client.post(
        "/api/v1/eintraege",
        json.dumps({"kategorie": "Pause", "start": f"{tag}T13:00:00", "ende": f"{tag}T13:15:00"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert antwort.status_code == 201 and antwort.json()["eintrag"]["nachgetragen"] is True
    api_timer = client.post(
        "/api/v1/start",
        json.dumps({"kategorie": "Mails"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert api_timer.json()["eintrag"]["nachgetragen"] is False


def test_merkmal_anteil_nachgetragen(nutzer, kat):
    tag = heute() - timedelta(days=1)
    e1 = Eintrag(
        nutzer=nutzer, kategorie=kat["Deep Work"], start=lokal(tag, 9), ende=lokal(tag, 10)
    )
    e2 = Eintrag(
        nutzer=nutzer,
        kategorie=kat["Mails"],
        start=lokal(tag, 10),
        ende=lokal(tag, 11),
        nachgetragen=True,
    )
    assert tagesmerkmale([e1, e2], [], timezone.now())["anteil_nachgetragen"] == 0.5
    assert tagesmerkmale([e1], [], timezone.now())["anteil_nachgetragen"] == 0


def test_muster_fussnote_bei_mehr_als_haelfte_nachgetragen(client, nutzer, kat):
    from .test_seiten import bewerte_tage

    bewerte_tage(nutzer, kat, 15)
    html = client.get(reverse("muster")).content.decode()
    assert "nachgetragen, also rekonstruiert" not in html
    Eintrag.objects.filter(nutzer=nutzer).update(nachgetragen=True)
    html = client.get(reverse("muster")).content.decode()
    assert "100 % der Einträge sind nachgetragen" in html and "Kahneman" in html


# --- Schlaf: Bett- und Aufstehzeit ------------------------------------------------------


def test_schlafdauer_und_schlafmitte():
    assert schlafdauer_h(time(23, 0), time(7, 0)) == 8.0
    assert schlafmitte(time(23, 0), time(7, 0)) == 180  # 03:00
    assert schlafdauer_h(time(0, 30), time(7, 42)) == 7.2
    assert schlafmitte(time(0, 30), time(8, 30)) == 270  # 04:30
    assert schlafmitte(time(22, 0), time(6, 0)) == 120  # 02:00
    assert schlafdauer_h(time(7, 0), time(7, 10)) is None  # unplausibel kurz
    assert schlafdauer_h(time(12, 0), time(20, 0)) is None  # 20 h, unplausibel
    assert schlafdauer_h(None, time(7, 0)) is None and schlafmitte(time(23), None) is None


def test_sozialer_jetlag():
    werk = [(True, 180)] * 5
    frei = [(False, 240), (False, 240), (False, 270)]
    assert sozialer_jetlag(werk + frei) == pytest.approx(250 - 180)
    assert sozialer_jetlag(werk + frei[:2]) is None  # zu wenige freie Tage
    assert sozialer_jetlag(werk[:2] + frei) is None


def test_letzter_kaffee_min():
    tag = date(2026, 11, 10)
    m = [
        Messung(zeitpunkt=lokal(tag, 9, 30), typ="kaffee", menge=1),
        Messung(zeitpunkt=lokal(tag, 14, 15), typ="kaffee", menge=1),
        Messung(zeitpunkt=lokal(tag, 20), typ="wasser_ml", menge=250),
    ]
    assert letzter_kaffee_min(m, tag) == 14 * 60 + 15
    assert letzter_kaffee_min(m[2:], tag) is None


def test_schlaf_wird_aus_zeiten_berechnet(client, nutzer):
    tag = heute()
    daten = {
        "produktivitaet": 6,
        "zufriedenheit": 7,
        "fortschritt": "True",
        "bettzeit": "23:15",
        "aufstehzeit": "06:45",
    }
    assert client.post(reverse("abschluss", args=[tag]), daten).status_code == 302
    b = Tagesbewertung.objects.get(nutzer=nutzer, datum=tag)
    assert float(b.schlaf_h) == 7.5 and b.bettzeit == time(23, 15)
    # ein eingegebener Wert gewinnt
    daten["schlaf_h"] = "6"
    client.post(reverse("abschluss", args=[tag]), daten)
    b.refresh_from_db()
    assert float(b.schlaf_h) == 6
    # unplausibel und ohne Stunden: Fehler
    daten.update(schlaf_h="", bettzeit="07:00", aufstehzeit="07:05")
    assert client.post(reverse("abschluss", args=[tag]), daten).status_code == 200


def test_schlaf_zeiten_ueber_api_und_merkmale(client, nutzer):
    from .test_seiten import lokal as _  # noqa: F401  (Import nur zur Sicherheit)

    token = ApiToken.erzeugen(nutzer, "t")[1]
    tag = heute()
    antwort = client.post(
        f"/api/v1/tag/{tag}/bewertung",
        json.dumps(
            {
                "produktivitaet": 6,
                "zufriedenheit": 7,
                "fortschritt": True,
                "bettzeit": "00:30",
                "aufstehzeit": "08:30",
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    b = antwort.json()["bewertung"]
    assert antwort.status_code == 201 and b["schlaf_h"] == 8.0 and b["bettzeit"] == "00:30"


def test_muster_schlaf_als_dritte_zielgroesse(client, nutzer, kat):
    from .test_seiten import bewerte_tage

    bewerte_tage(nutzer, kat, 20)
    for i, b in enumerate(Tagesbewertung.objects.filter(nutzer=nutzer)):
        b.schlaf_h = 5 + (i % 5) * 0.5 if i % 4 else None  # Lücken: nur Tage mit Schlaf zählen
        b.bettzeit, b.aufstehzeit = time(23, 0), time(7, 0)
        b.save()
    antwort = client.get(reverse("muster") + "?ziel=schlaf_h")
    html = antwort.content.decode()
    assert antwort.status_code == 200 and "Schlaf" in html
    assert antwort.context["ergebnis"]["n"] == 15  # 20 minus 5 Tage ohne Schlaf
    schluessel = {z["key"] for z in antwort.context["ergebnis"]["zeilen"]}
    assert not schluessel & {"schlaf_h", "schlaf_schnitt_7", "schlafmitte"}
    assert "Schlaf" in dict(antwort.context["ziele"].items()).values()


def test_muster_sozialer_jetlag_angezeigt(client, nutzer, kat):
    # 6 Werktage mit Arbeit und Schlafmitte 03:00, 3 freie Tage ohne Arbeit mit 04:00
    for i in range(1, 10):
        tag = heute() - timedelta(days=i)
        werktag = i <= 6
        bewerte(
            nutzer, tag,
            bettzeit=time(23, 0) if werktag else time(0, 0),
            aufstehzeit=time(7, 0) if werktag else time(8, 0),
        )  # fmt: skip
        if werktag:
            Eintrag.objects.create(
                nutzer=nutzer, kategorie=kat["Deep Work"], start=lokal(tag, 9), ende=lokal(tag, 10)
            )
    html = client.get(reverse("muster")).content.decode()
    assert "Sozialer Jetlag der letzten 28 Tage: <strong>+1 h 00 min</strong>" in html


# --- API -------------------------------------------------------------------------------


@pytest.fixture
def token(nutzer):
    return ApiToken.erzeugen(nutzer, "test")[1]


def api_get(client, token, pfad, **abfrage):
    return client.get("/api/v1/" + pfad, abfrage, HTTP_AUTHORIZATION=f"Bearer {token}")


def api_post(client, token, pfad, daten):
    return client.post(
        "/api/v1/" + pfad,
        json.dumps(daten),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


def test_api_experiment_start_status_und_bestaetigen(client, nutzer, token):
    antwort = api_get(client, token, "experiment")
    j = antwort.json()
    assert j["laufend"] is None and len(j["vorlagen"]) == 8 and j["beendete"] == []
    assert {"key", "titel", "regel", "hinweis"} <= set(j["vorlagen"][0])

    antwort = api_post(client, token, "experiment", {"vorlage": "mikropausen"})
    assert antwort.status_code == 201
    e = antwort.json()["experiment"]
    assert e["status"] == "laeuft" and len(e["tage"]) == 20 and e["heute"]["bedingung"] in "AB"
    zweites = api_post(client, token, "experiment", {"vorlage": "mikropausen"})
    assert zweites.status_code == 400 and "läuft schon" in zweites.json()["fehler"]
    assert api_post(client, token, "experiment", {"vorlage": "gibtsnicht"}).status_code == 400

    antwort = api_post(client, token, f"experiment/tag/{heute()}", {"eingehalten": True})
    assert antwort.status_code == 200 and antwort.json()["eingehalten"] is True
    assert (
        api_post(client, token, f"experiment/tag/{heute()}", {"eingehalten": "ja"}).status_code
        == 400
    )
    assert (
        api_post(client, token, "experiment/tag/2000-01-01", {"eingehalten": True}).status_code
        == 404
    )
    laufend = api_get(client, token, "experiment").json()["laufend"]
    assert laufend["einhaltung"] == {"antworten": 1, "ja": 1}


def test_api_experiment_eigene_felder_und_validierung(client, nutzer, token):
    antwort = api_post(client, token, "experiment", {"titel": "Nur Titel"})
    assert antwort.status_code == 400 and antwort.json()["felder"]
    antwort = api_post(
        client,
        token,
        "experiment",
        {
            "titel": "Spazieren",
            "hypothese": "Mehr Energie",
            "regel_wenn": "ich mittags esse",
            "regel_dann": "gehe ich 10 Minuten raus",
            "design": "bloecke",
            "blocklaenge": 2,
            "dauer_tage": 14,
            "zielgroesse": "zufriedenheit",
        },
    )
    assert antwort.status_code == 201
    e = antwort.json()["experiment"]
    assert e["regel"] == "Wenn ich mittags esse, dann gehe ich 10 Minuten raus."
    assert e["fortschritt"] == {"tag": 1, "von": 14}


def test_api_fremdes_experiment_unsichtbar_und_tag_404(client, nutzer, fremder, token):
    neues_experiment(fremder)
    assert api_get(client, token, "experiment").json()["laufend"] is None
    assert (
        api_post(client, token, f"experiment/tag/{heute()}", {"eingehalten": True}).status_code
        == 404
    )
    fremd = ExperimentTag.objects.get(experiment__nutzer=fremder, datum=heute())
    assert fremd.eingehalten is None


def test_api_beendete_mit_ergebnis(client, nutzer, token):
    beendetes_experiment(nutzer)
    j = api_get(client, token, "experiment").json()
    assert j["laufend"] is None and len(j["beendete"]) == 1
    erg = j["beendete"][0]["ergebnis"]
    assert erg["aussage"] == "dafuer" and erg["differenz_b_minus_a"] == 3.5
    assert 0 < erg["p"] < 0.05 and "Beweis" in erg["text"]


def test_api_plan_enthaelt_plan_faktor(client, nutzer, token, kat):
    for i in range(1, 8):
        tag = heute() - timedelta(days=i)
        Planblock.objects.create(
            nutzer=nutzer, kategorie=kat["Deep Work"], start=lokal(tag, 9), ende=lokal(tag, 11)
        )
        Eintrag.objects.create(
            nutzer=nutzer, kategorie=kat["Deep Work"], start=lokal(tag, 9), ende=lokal(tag, 10, 24)
        )
    j = api_get(
        client, token, "plan", start=str(heute() - timedelta(days=3)), ende=str(heute())
    ).json()
    (faktor,) = j["plan_faktor"]
    assert faktor["art"] == "deepwork" and faktor["faktor"] == 0.7 and faktor["tage"] == 7
    assert "70 %" in faktor["text"]


def test_api_wochenbericht(client, nutzer, token, kat, django_assert_max_num_queries):
    from .test_seiten import bewerte_tage

    bewerte_tage(nutzer, kat, 20)
    neues_experiment(nutzer)
    with django_assert_max_num_queries(60):
        antwort = api_get(client, token, f"wochenbericht/{heute() - timedelta(days=3)}")
    j = antwort.json()
    assert antwort.status_code == 200
    assert len(j["woche"]["tage"]) == 7 and "merkmale" in next(
        t for t in j["woche"]["tage"] if t["bewertet"]
    )
    assert j["laufendes_experiment"]["titel"] == "Mikropausen"
    assert len(j["experiment_vorlagen"]) == 8
    assert len(j["muster_hinweise"]) == 2 and j["muster_hinweise"][0]["ziel"] == "produktivitaet"
    assert "keine Ursachen" in j["hinweis"]
    assert j["vergleich_vorherige_4_wochen"]["bewertete_tage"] > 0
    assert api_get(client, token, "wochenbericht/kaputt").status_code == 404


def test_api_wochenbericht_ohne_daten_und_ohne_token(client, nutzer, token):
    j = api_get(client, token, f"wochenbericht/{heute()}").json()
    assert all(not t["bewertet"] for t in j["woche"]["tage"])
    assert j["laufendes_experiment"] is None
    assert client.get(f"/api/v1/wochenbericht/{heute()}").status_code == 401
    assert client.get("/api/v1/experiment").status_code == 401


# --- Demodaten ---------------------------------------------------------------------------


def test_demodaten_experimente_plan_und_schlaf():
    from tracking.experiment_views import experiment_ergebnis, experiment_werte
    from tracking.views import _plan_faktor

    call_command("demodaten", "demo", stdout=io.StringIO())
    demo = get_user_model().objects.get(username="demo")
    assert Experiment.objects.filter(nutzer=demo, status="laeuft").count() == 1
    mikro = Experiment.objects.prefetch_related("tage").get(nutzer=demo, titel="Mikropausen")
    assert mikro.status == "beendet" and mikro.tage.count() == 20
    assert Experiment.objects.get(nutzer=demo, status="laeuft").titel == "Koffein-Schluss"
    erg = experiment_ergebnis(mikro, experiment_werte(demo, [mikro], timezone.now())[mikro.pk])
    assert erg["differenz"] > 0 and erg["aussage"] in ("dafuer", "hinweis")
    assert erg["n_a"] + erg["n_b"] == 20  # Experimenttage sind immer erfasst
    faktoren = {f["art"]: f for f in _plan_faktor(demo, timezone.now())}
    assert 0.6 <= faktoren["deepwork"]["faktor"] <= 0.8
    assert Eintrag.objects.filter(nutzer=demo, nachgetragen=True).exists()
    assert Eintrag.objects.filter(nutzer=demo, nachgetragen=False).exists()
    bew = Tagesbewertung.objects.filter(nutzer=demo)
    assert bew.exclude(bettzeit=None).exists() and bew.filter(bettzeit=None).exists()
    b = bew.exclude(bettzeit=None).first()
    assert schlafdauer_h(b.bettzeit, b.aufstehzeit) == float(b.schlaf_h)
    with pytest.raises(Exception, match="schon Daten"):
        call_command("demodaten", "demo")


def test_kleinstes_p_je_design():
    assert statistik.kleinstes_p("abab", 28, 7) == 1.0
    assert statistik.kleinstes_p("bloecke", 56, 7) == pytest.approx(2 / 70)
    assert statistik.kleinstes_p("tageweise", 20, 1) == pytest.approx(2 / 184756)
    assert statistik.kleinstes_p("bloecke", 30, 7) is None


def test_vorlagen_sind_bestaetigungsfaehig():
    for key, v in experimente.VORLAGEN.items():
        assert experimente.design_fehler(v["design"], v["dauer"], v["blocklaenge"]) is None, key
        assert statistik.kleinstes_p(v["design"], v["dauer"], v["blocklaenge"]) <= 0.05, key


def test_experiment_formular_zeigt_kleinstes_p_und_abab_warnung(client):
    html = client.get(reverse("experiment_neu") + "?vorlage=plan_puffer").content.decode()
    assert "0,029" in html and "kann statistisch nichts bestätigen" not in html
    teil = client.get(
        reverse("experiment_design_hinweis"), {"design": "abab", "blocklaenge": "7"}
    ).content.decode()
    assert "1,000" in teil and "kann statistisch nichts bestätigen, nur beschreiben" in teil
    assert (
        client.get(reverse("experiment_design_hinweis"), {"design": "abab"}).content.strip() == b""
    )


def _getrennte_werte(z, seed=7):
    """Alle B-Werte weit über allen A-Werten, innerhalb der Gruppen zufällig gestreut."""
    zufall = random.Random(seed)
    return [(1000.0 if g == "B" else 0.0) + zufall.random() * 100 for g in z]


@pytest.mark.parametrize(
    ("design", "dauer", "laenge"),
    [("abab", 28, 7), ("bloecke", 56, 7), ("bloecke", 32, 4), ("bloecke", 30, 5)],
)
def test_kleinstes_p_stimmt_mit_echtem_test_bei_maximaler_trennung(design, dauer, laenge):
    z = experimente.zuweisung(design, dauer, laenge, random.Random(4))
    test = statistik.randomisierungstest(_getrennte_werte(z), z, design, laenge)
    assert test["exakt"]
    assert test["p"] == pytest.approx(statistik.kleinstes_p(design, dauer, laenge))
    assert test["p_min"] == pytest.approx(test["p"])


@pytest.mark.parametrize("dauer", [8, 10, 12])
def test_kleinstes_p_tageweise_ist_untergrenze(dauer):
    z = experimente.zuweisung("tageweise", dauer, 1, random.Random(4))
    test = statistik.randomisierungstest(_getrennte_werte(z), z, "tageweise", 1)
    assert test["p"] >= statistik.kleinstes_p("tageweise", dauer, 1) - 1e-12
