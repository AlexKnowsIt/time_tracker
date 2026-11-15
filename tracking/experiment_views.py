"""Seiten und gemeinsame Hilfen für Selbstexperimente (Zielbild Stufe 4, docs/forschung.md).

Die Auswertung selbst steckt in ``experimente.py``/``statistik.py`` (reine Funktionen); hier
kommen nur die Werte je Tag aus der Datenbank und die Aufbereitung für Seite und API.
"""

import random
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import experimente, statistik
from .forms import AbbruchForm, ExperimentForm
from .merkmale import formatiere, tagesmerkmale
from .models import Experiment, Tagesbewertung
from .plan import plan_vs_ist
from .services import (
    beende_abgelaufene_experimente,
    breche_experiment_ab,
    starte_experiment,
)
from .views import _nach_tagen, _planbloecke
from .zeit import tagesdatum, tagesgrenzen

FORMULAR_FELDER = ("titel", "hypothese", "regel_wenn", "regel_dann", "bedingung_a", "design")


def experiment_werte(nutzer, experiment_liste, jetzt):
    """Wert der Zielgröße je Tag: {experiment.pk: {datum: wert | None}}, mit konstant vielen
    Abfragen (die Tage sind per prefetch_related("tage") vorgeladen).

    Zielgrößen aus Tagesmerkmalen und Plan gibt es nur für bewertete Tage (Score vor Statistik).
    Schlaf der folgenden Nacht steht in der Bewertung des Folgetags.
    """
    datums = [t.datum for e in experiment_liste for t in e.tage.all()]
    if not datums:
        return {e.pk: {} for e in experiment_liste}
    von, bis = min(datums), max(datums)
    bewertungen = {
        b.datum: b
        for b in Tagesbewertung.objects.filter(
            nutzer=nutzer, datum__range=(von, bis + timedelta(days=1))
        )
    }
    quellen = {experimente.ZIELE[e.zielgroesse][2] for e in experiment_liste}
    eintraege = messungen = plan = None
    if quellen & {"merkmal", "plan"}:
        eintraege, messungen = _nach_tagen(nutzer, von, bis)
    if "plan" in quellen:
        plan = {}
        for block in _planbloecke(nutzer, tagesgrenzen(von)[0], tagesgrenzen(bis)[1]):
            plan.setdefault(tagesdatum(block.start), []).append(block)

    def wert(ziel, quelle, tag):
        b = bewertungen.get(tag)
        if quelle == "bewertung":
            return getattr(b, ziel) if b else None
        if quelle == "folgenacht":
            folge = bewertungen.get(tag + timedelta(days=1))
            return float(folge.schlaf_h) if folge and folge.schlaf_h is not None else None
        if b is None:
            return None
        if quelle == "merkmal":
            return tagesmerkmale(eintraege.get(tag, []), messungen.get(tag, []), jetzt)[ziel]
        blocks = plan.get(tag)
        if not blocks:
            return None
        zeilen = plan_vs_ist(blocks, eintraege.get(tag, []), *tagesgrenzen(tag), jetzt)
        geplant = sum(z["geplant"] for z in zeilen)
        erfasst = sum(z["erfasst"] for z in zeilen if z["geplant"] > 0)
        return erfasst / geplant if geplant else None

    return {
        e.pk: {
            t.datum: wert(e.zielgroesse, experimente.ZIELE[e.zielgroesse][2], t.datum)
            for t in e.tage.all()
        }
        for e in experiment_liste
    }


def experiment_ergebnis(experiment, werte):
    """Auswertung eines beendeten Experiments; ``werte`` = {datum: wert}. Deterministisch
    über den Seed des Experiments."""
    tage = [(t.bedingung, werte.get(t.datum), t.eingehalten) for t in experiment.tage.all()]
    return experimente.auswerten(
        tage,
        experiment.design,
        experiment.blocklaenge,
        experiment.zielgroesse,
        random.Random(experiment.seed),
    )


def _prozent(anteil):
    return None if anteil is None else round(anteil * 100)


def ergebnis_anzeige(erg, zielgroesse):
    """Ergebnis mit fertigen Texten für Seite und API."""
    format = erg["format"]
    p = erg["p"]
    p_text = None if p is None else "< 0,001" if p < 0.001 else f"{p:.3f}".replace(".", ",")
    if erg["exakt"] is None:
        verfahren = None
    elif erg["exakt"]:
        verfahren = f"exakt über alle {erg['n_zuweisungen']} zulässigen Zuweisungen"
    else:
        gesamt = f"{erg['n_zuweisungen']:,}".replace(",", ".")
        verfahren = f"{experimente.N_PERM} zufällige Zuweisungen von {gesamt} möglichen"
    protokoll = erg["protokoll"]
    return {
        **erg,
        "median_a_text": formatiere(erg["median_a"], format),
        "median_b_text": formatiere(erg["median_b"], format),
        "differenz_text": experimente.diff_text(erg["differenz"], format),
        "p_text": p_text,
        "verfahren": verfahren,
        "einhaltung_b_prozent": _prozent(erg["einhaltung_b"]),
        "einhaltung_a_prozent": _prozent(erg["einhaltung_a"]),
        "protokoll_text": (
            f"{experimente.diff_text(protokoll['differenz'], format)} "
            f"(A {protokoll['n_a']}, B {protokoll['n_b']} Tage)"
            if protokoll
            else None
        ),
    }


def design_hinweis(design, blocklaenge, dauer):
    """Kleinstes erreichbares p des gewählten Designs (für das Formular) plus Warnung bei ABAB.
    None, wenn die Angaben noch unvollständig sind."""
    if design not in (experimente.TAGEWEISE, experimente.BLOECKE, experimente.ABAB):
        return None
    laenge = 1 if design == experimente.TAGEWEISE else blocklaenge
    if design == experimente.ABAB and laenge:
        dauer = 4 * laenge
    if not dauer or not laenge or experimente.design_fehler(design, dauer, laenge):
        return None
    p = statistik.kleinstes_p(design, dauer, laenge)
    return {
        "p_text": f"{p:.3f}".replace(".", ","),
        "abab": design == experimente.ABAB,
        "kann_bestaetigen": p <= experimente.HYPOTHESE_P,
    }


def _zahl(wert):
    try:
        return int(wert)
    except (TypeError, ValueError):
        return None


@login_required
def design_hinweis_teil(request):
    """HTMX-Teil: Hinweis zum gewählten Design, wird bei jeder Änderung im Formular geladen."""
    g = request.GET
    hinweis = design_hinweis(
        g.get("design"), _zahl(g.get("blocklaenge")), _zahl(g.get("dauer_tage"))
    )
    return render(request, "tracking/_experiment_design_hinweis.html", {"hinweis": hinweis})


def vorlagen_liste():
    return [
        {
            "key": key,
            **v,
            "ziel_label": experimente.ZIELE[v["ziel"]][0],
            "design_text": design_text(v["design"], v["blocklaenge"], v["dauer"]),
            "regel": f"Wenn {v['wenn']}, dann {v['dann']}.",
        }
        for key, v in experimente.VORLAGEN.items()
    ]


def design_text(design, blocklaenge, dauer):
    if design == experimente.TAGEWEISE:
        return f"tageweise zufällig, {dauer} Tage"
    if design == experimente.BLOECKE:
        return f"{blocklaenge}-Tages-Blöcke zufällig, {dauer} Tage"
    return f"ABAB, Phasen à {blocklaenge} Tage, {dauer} Tage"


def fortschritt(experiment, heute):
    """Tag x von y (nur sinnvoll, solange es läuft)."""
    gemacht = max(0, min(experiment.dauer_tage, (heute - experiment.start).days + 1))
    return {"tag": gemacht, "von": experiment.dauer_tage}


def _liste(nutzer):
    return list(Experiment.objects.filter(nutzer=nutzer).prefetch_related("tage"))


@login_required
def liste(request):
    jetzt = timezone.now()
    heute = tagesdatum(jetzt)
    beende_abgelaufene_experimente(request.user, heute)
    alle = _liste(request.user)
    laufend = next((e for e in alle if e.status == Experiment.Status.LAEUFT), None)
    beendete = [e for e in alle if e.status == Experiment.Status.BEENDET]
    abgebrochene = [e for e in alle if e.status == Experiment.Status.ABGEBROCHEN]
    werte = experiment_werte(request.user, beendete, jetzt)
    return render(
        request,
        "tracking/experimente.html",
        {
            "laufend": laufend and _laufend_kontext(laufend, heute),
            "beendete": [
                {
                    "experiment": e,
                    "ergebnis": ergebnis_anzeige(
                        experiment_ergebnis(e, werte[e.pk]), e.zielgroesse
                    ),
                    "ziel_label": experimente.ZIELE[e.zielgroesse][0],
                }
                for e in beendete
            ],
            "abgebrochene": abgebrochene,
            "vorlagen": vorlagen_liste(),
        },
    )


def _laufend_kontext(experiment, heute):
    tage = list(experiment.tage.all())
    heute_tag = next((t for t in tage if t.datum == heute), None)
    antworten = [t for t in tage if t.datum <= heute and t.eingehalten is not None]
    return {
        "experiment": experiment,
        "ziel_label": experimente.ZIELE[experiment.zielgroesse][0],
        "fortschritt": fortschritt(experiment, heute),
        "heute": heute_tag,
        "beginnt_am": experiment.start if experiment.start > heute else None,
        "antworten": len(antworten),
        "eingehalten": sum(1 for t in antworten if t.eingehalten),
        "design_text": design_text(
            experiment.design, experiment.blocklaenge, experiment.dauer_tage
        ),
    }


@login_required
def neu(request):
    vorlage = experimente.VORLAGEN.get(request.GET.get("vorlage", ""))
    initial = {}
    if vorlage:
        initial = {
            "titel": vorlage["titel"],
            "hypothese": vorlage["hypothese"],
            "regel_wenn": vorlage["wenn"],
            "regel_dann": vorlage["dann"],
            "design": vorlage["design"],
            "blocklaenge": vorlage["blocklaenge"],
            "dauer_tage": vorlage["dauer"],
            "zielgroesse": vorlage["ziel"],
        }
    form = ExperimentForm(request.POST or None, initial=initial, nutzer=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            starte_experiment(
                request.user, **{k: form.cleaned_data[k] for k in FORMULAR_FELDER + _ZAHLEN}
            )
        except ValueError as fehler:
            form.add_error(None, str(fehler))
        else:
            return redirect("experimente")
    return render(
        request,
        "tracking/experiment_form.html",
        {
            "form": form,
            "vorlage": vorlage,
            "ziele": experimente.ZIELE,
            "hinweis": design_hinweis(
                form["design"].value(),
                _zahl(form["blocklaenge"].value()),
                _zahl(form["dauer_tage"].value()),
            ),
        },
    )


_ZAHLEN = ("blocklaenge", "dauer_tage", "zielgroesse", "start")


@login_required
def detail(request, pk, abbruch_form=None):
    jetzt = timezone.now()
    heute = tagesdatum(jetzt)
    beende_abgelaufene_experimente(request.user, heute)
    experiment = get_object_or_404(
        Experiment.objects.prefetch_related("tage"), pk=pk, nutzer=request.user
    )
    beendet = experiment.status == Experiment.Status.BEENDET
    format = experimente.ZIELE[experiment.zielgroesse][1]
    werte = experiment_werte(request.user, [experiment], jetzt)[experiment.pk] if beendet else {}
    ergebnis = (
        ergebnis_anzeige(experiment_ergebnis(experiment, werte), experiment.zielgroesse)
        if beendet
        else None
    )
    kontext = {
        "experiment": experiment,
        "ziel_label": experimente.ZIELE[experiment.zielgroesse][0],
        "design_text": design_text(
            experiment.design, experiment.blocklaenge, experiment.dauer_tage
        ),
        "laufend": _laufend_kontext(experiment, heute),
        # Ergebnis erst nach dem Ende: Zwischenstände würden das Verhalten lenken
        "ergebnis": ergebnis,
        "tage": [
            {
                "tag": t,
                "heute": t.datum == heute,
                "wert": formatiere(werte[t.datum], format)
                if werte.get(t.datum) is not None
                else None,
            }
            for t in experiment.tage.all()
        ],
        "abbruch_form": abbruch_form or AbbruchForm(),
    }
    return render(request, "tracking/experiment_detail.html", kontext)


@login_required
@require_POST
def abbrechen(request, pk):
    experiment = get_object_or_404(Experiment, pk=pk, nutzer=request.user)
    form = AbbruchForm(request.POST)
    if form.is_valid():
        try:
            breche_experiment_ab(experiment, form.cleaned_data["vermerk"])
        except ValueError as fehler:
            form.add_error(None, str(fehler))
        else:
            return redirect("experiment_detail", pk=pk)
    return detail(request, pk, abbruch_form=form)
