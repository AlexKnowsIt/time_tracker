from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .auswertung import MIN_TAGE, vergleich
from .forms import BewertungForm, EintragForm, PlanblockForm, TokenForm
from .merkmale import formatiere, tagesmerkmale
from .models import ApiToken, Eintrag, Kategorie, Messung, Planblock, Tagesbewertung
from .plan import plan_vs_ist
from .services import starte_eintrag, stoppe_eintrag
from .zeit import dauer_text, tagesdatum, tagesgrenzen

# Messungs-Knöpfe: Typ -> Menge pro Tipp
MESSUNG_KNOEPFE = {Messung.Typ.WASSER_ML: 250, Messung.Typ.KAFFEE: 1}


def manifest(request):
    return JsonResponse(
        {
            "name": "Zeiterfassung",
            "short_name": "Zeit",
            "start_url": "/",
            "display": "standalone",
            "theme_color": "#1f4e8c",
            "background_color": "#f6f7f9",
            "lang": "de",
            "icons": [
                {
                    "src": static("tracking/icon.svg"),
                    "sizes": "any",
                    "type": "image/svg+xml",
                    "purpose": "any",
                }
            ],
        },
        content_type="application/manifest+json",
    )


def _antwort(request):
    """HTMX bekommt das Teil-Template, ohne JS gibt es Redirect (PRG)."""
    if request.headers.get("HX-Request"):
        return render(request, "tracking/_jetzt.html", _jetzt_kontext(request.user))
    return redirect("jetzt")


def _jetzt_kontext(nutzer):
    jetzt = timezone.now()
    beginn, ende = tagesgrenzen(tagesdatum(jetzt))
    heute = Messung.objects.filter(nutzer=nutzer, zeitpunkt__gte=beginn, zeitpunkt__lt=ende)
    summen = {
        m["typ"]: m["summe"] for m in heute.values("typ").annotate(summe=Sum("menge")).order_by()
    }
    kategorien = Kategorie.objects.filter(nutzer=nutzer, aktiv=True).annotate(
        haeufigkeit=Count("eintrag", filter=Q(eintrag__start__gte=jetzt - timedelta(days=30)))
    )
    return {
        "laufend": Eintrag.objects.filter(nutzer=nutzer, ende=None)
        .select_related("kategorie")
        .first(),
        "kategorien": kategorien.order_by("-haeufigkeit", "name"),
        "wasser_ml": summen.get(Messung.Typ.WASSER_ML, 0),
        "kaffee": summen.get(Messung.Typ.KAFFEE, 0),
    }


@login_required
def jetzt(request):
    kontext = _jetzt_kontext(request.user)
    if request.headers.get("HX-Request"):
        return render(request, "tracking/_jetzt.html", kontext)
    return render(request, "tracking/jetzt.html", kontext)


@login_required
@require_POST
def start(request, pk):
    kategorie = get_object_or_404(Kategorie, pk=pk, nutzer=request.user, aktiv=True)
    starte_eintrag(request.user, kategorie)
    return _antwort(request)


@login_required
@require_POST
def stopp(request):
    stoppe_eintrag(request.user)
    return _antwort(request)


@login_required
@require_POST
def messung(request):
    typ = request.POST.get("typ")
    if typ not in MESSUNG_KNOEPFE:
        return redirect("jetzt")
    Messung.objects.create(
        nutzer=request.user, zeitpunkt=timezone.now(), typ=typ, menge=MESSUNG_KNOEPFE[typ]
    )
    return _antwort(request)


def _planbloecke(nutzer, beginn, ende):
    """Planblöcke, die [beginn, ende) berühren, nach Start sortiert."""
    return list(
        Planblock.objects.filter(nutzer=nutzer, start__lt=ende, ende__gt=beginn)
        .select_related("kategorie")
        .order_by("start")
    )


def _zeitleiste(eintraege, jetzt):
    """Blöcke und Lücken von erstem Start bis letztem Ende. flex-grow = Sekunden."""
    if not eintraege:
        return None
    segmente, luecke_s, cursor = [], 0, None
    for e in sorted(eintraege, key=lambda e: e.start):
        ende = e.ende or jetzt
        if cursor is None:
            cursor = e.start
        beginn = max(e.start, cursor)
        if beginn > cursor:
            s = (beginn - cursor).total_seconds()
            luecke_s += s
            segmente.append(
                {"luecke": True, "sekunden": s, "text": f"nicht erfasst, {dauer_text(s)}"}
            )
        s = (ende - beginn).total_seconds()
        if s > 0:
            segmente.append(
                {
                    "eintrag": e,
                    "sekunden": s,
                    "text": f"{e.kategorie.name}, {dauer_text(s)}",
                }
            )
            cursor = ende
    return {
        "segmente": segmente,
        "von": eintraege[0].start,
        "bis": cursor,
        "luecke": dauer_text(luecke_s) if luecke_s else None,
    }


def _zusammenfassung(eintraege, wasser_ml, bewertung, jetzt):
    pro_art = {}
    for e in eintraege:
        sekunden = ((e.ende or jetzt) - e.start).total_seconds()
        pro_art[e.kategorie.art] = pro_art.get(e.kategorie.art, 0) + sekunden
    return {
        "arten": [
            (label, dauer_text(pro_art[art]))
            for art, label in Kategorie.Art.choices
            if art in pro_art
        ],
        "gesamt": dauer_text(sum(pro_art.values())),
        "wasser_ml": wasser_ml,
        "bewertung": bewertung,
    }


@login_required
def tag(request, datum=None):
    jetzt = timezone.now()
    datum = datum or tagesdatum(jetzt)
    beginn, ende = tagesgrenzen(datum)
    eintraege = list(
        Eintrag.objects.filter(nutzer=request.user, start__gte=beginn, start__lt=ende)
        .select_related("kategorie")
        .order_by("start")
    )
    messungen = list(
        Messung.objects.filter(
            nutzer=request.user, zeitpunkt__gte=beginn, zeitpunkt__lt=ende
        ).order_by("zeitpunkt")
    )
    wasser = sum(m.menge for m in messungen if m.typ == Messung.Typ.WASSER_ML)
    bewertung = Tagesbewertung.objects.filter(nutzer=request.user, datum=datum).first()
    # Plan/Ist ist keine Score-Statistik und erscheint immer, sobald es Planblöcke gibt.
    planbloecke = _planbloecke(request.user, beginn, ende)
    plan_ist = None
    if planbloecke:
        ist = _eintraege_im_zeitraum(request.user, beginn, ende)
        plan_ist = plan_vs_ist(planbloecke, ist, beginn, ende, jetzt)
    return render(
        request,
        "tracking/tag.html",
        {
            "datum": datum,
            "vortag": datum - timedelta(days=1),
            "folgetag": datum + timedelta(days=1),
            "zeilen": [
                {"eintrag": e, "dauer": dauer_text(((e.ende or jetzt) - e.start).total_seconds())}
                for e in eintraege
            ],
            "zeitleiste": _zeitleiste(eintraege, jetzt),
            "messungen": messungen,
            "plan_ist": plan_ist,
            "zusammenfassung": _zusammenfassung(eintraege, wasser, bewertung, jetzt)
            if bewertung
            else None,
        },
    )


@login_required
def eintrag_form(request, pk=None, datum=None):
    eintrag = get_object_or_404(Eintrag, pk=pk, nutzer=request.user) if pk else None
    if eintrag:
        datum = tagesdatum(eintrag.start)
    initial = {} if eintrag else {"start": tagesgrenzen(datum)[0] + timedelta(hours=5)}
    form = EintragForm(request.POST or None, instance=eintrag, initial=initial, nutzer=request.user)
    if request.method == "POST" and form.is_valid():
        gespeichert = form.save(commit=False)
        gespeichert.nutzer = request.user
        gespeichert.save()
        return redirect("tag", datum=tagesdatum(gespeichert.start))
    return render(
        request, "tracking/eintrag_form.html", {"form": form, "eintrag": eintrag, "datum": datum}
    )


@login_required
@require_POST
def eintrag_loeschen(request, pk):
    eintrag = get_object_or_404(Eintrag, pk=pk, nutzer=request.user)
    datum = tagesdatum(eintrag.start)
    eintrag.delete()
    return redirect("tag", datum=datum)


@login_required
def abschluss_heute(request):
    return redirect("abschluss", datum=tagesdatum(timezone.now()))


@login_required
def abschluss(request, datum):
    bewertung = Tagesbewertung.objects.filter(nutzer=request.user, datum=datum).first()
    form = BewertungForm(request.POST or None, instance=bewertung)
    if request.method == "POST" and form.is_valid():
        gespeichert = form.save(commit=False)
        gespeichert.nutzer, gespeichert.datum = request.user, datum
        gespeichert.save()
        return redirect("tag", datum=datum)
    return render(request, "tracking/abschluss.html", {"form": form, "datum": datum})


@login_required
@require_POST
def messung_loeschen(request, pk):
    m = get_object_or_404(Messung, pk=pk, nutzer=request.user)
    datum = tagesdatum(m.zeitpunkt)
    m.delete()
    return redirect("tag", datum=datum)


def _nach_tagen(nutzer, von, bis):
    """Einträge und Messungen der Tage von..bis (inklusive) mit je einer Abfrage, nach Tag."""
    beginn, ende = tagesgrenzen(von)[0], tagesgrenzen(bis)[1]
    eintraege, messungen = {}, {}
    for e in (
        Eintrag.objects.filter(nutzer=nutzer, start__gte=beginn, start__lt=ende)
        .select_related("kategorie")
        .order_by("start")
    ):
        eintraege.setdefault(tagesdatum(e.start), []).append(e)
    for m in Messung.objects.filter(
        nutzer=nutzer, zeitpunkt__gte=beginn, zeitpunkt__lt=ende
    ).order_by("zeitpunkt"):
        messungen.setdefault(tagesdatum(m.zeitpunkt), []).append(m)
    return eintraege, messungen


def _woche_daten(nutzer, datum, jetzt):
    """Montag bis Sonntag der Woche von ``datum``: je Tag Einträge, Bewertung, Deep-Work-Minuten."""
    montag = datum - timedelta(days=datum.weekday())
    sonntag = montag + timedelta(days=6)
    eintraege, _ = _nach_tagen(nutzer, montag, sonntag)
    bewertungen = {
        b.datum: b
        for b in Tagesbewertung.objects.filter(nutzer=nutzer, datum__range=(montag, sonntag))
    }
    tage = []
    for i in range(7):
        tag_datum = montag + timedelta(days=i)
        tag_eintraege = eintraege.get(tag_datum, [])
        bewertung = bewertungen.get(tag_datum)
        deepwork = None
        if bewertung:  # Statistik des Tages erst nach der Bewertung (AGENTS.md)
            deepwork = tagesmerkmale(tag_eintraege, [], jetzt)["deepwork_min"]
        tage.append(
            {
                "datum": tag_datum,
                "eintraege": tag_eintraege,
                "bewertung": bewertung,
                "deepwork_min": deepwork,
            }
        )
    return montag, sonntag, tage


@login_required
def woche(request, datum=None):
    jetzt = timezone.now()
    montag, sonntag, tage = _woche_daten(request.user, datum or tagesdatum(jetzt), jetzt)
    return render(
        request,
        "tracking/woche.html",
        {
            "montag": montag,
            "sonntag": sonntag,
            "vorwoche": montag - timedelta(days=7),
            "folgewoche": montag + timedelta(days=7),
            "tage": [
                {
                    "datum": t["datum"],
                    "zeitleiste": _zeitleiste(t["eintraege"], jetzt),
                    "bewertung": t["bewertung"],
                    "deepwork": dauer_text(t["deepwork_min"] * 60)
                    if t["deepwork_min"] is not None
                    else None,
                }
                for t in tage
            ],
        },
    )


ZIELGROESSEN = {
    "produktivitaet": "Produktivität",
    "zufriedenheit": "Zufriedenheit",
}
MUSTER_TAGE = 180


def _muster_kontext(nutzer, ziel, jetzt):
    """Auswertung für die Muster-Seite und die API; ``ziel`` muss in ZIELGROESSEN sein."""
    heute = tagesdatum(jetzt)
    von = heute - timedelta(days=MUSTER_TAGE - 1)
    # Ein Tag früher, damit auch der Vortag des ersten Tages bekannt ist.
    bewertungen = {
        b["datum"]: b
        for b in Tagesbewertung.objects.filter(
            nutzer=nutzer, datum__range=(von - timedelta(days=1), heute)
        ).values("datum", "produktivitaet", "zufriedenheit", "schlaf_h")
    }
    kontext = {
        "ziel": ziel,
        "ziel_label": ZIELGROESSEN[ziel],
        "ziele": ZIELGROESSEN,
        "tage_max": MUSTER_TAGE,
        "min_tage": MIN_TAGE,
    }
    bewertete = sorted(d for d in bewertungen if d >= von)
    if len(bewertete) < MIN_TAGE:
        kontext["fehlend"] = MIN_TAGE - len(bewertete)
        kontext["bewertet"] = len(bewertete)
        return kontext

    eintraege, messungen = _nach_tagen(nutzer, bewertete[0], bewertete[-1])
    tage = []
    for d in bewertete:
        m = tagesmerkmale(eintraege.get(d, []), messungen.get(d, []), jetzt)
        b = bewertungen[d]
        m["schlaf_h"] = float(b["schlaf_h"]) if b["schlaf_h"] is not None else None
        vortag = bewertungen.get(d - timedelta(days=1))
        m["produktivitaet_vortag"] = vortag["produktivitaet"] if vortag else None
        tage.append((b, m))
    ergebnis = vergleich(tage, ziel)
    ergebnis["zeilen"] = [
        {
            **z,
            "gut_text": formatiere(z["gut"], z["format"]),
            "schwach_text": formatiere(z["schwach"], z["format"]),
        }
        for z in ergebnis["zeilen"]
    ]
    kontext.update(
        ergebnis=ergebnis,
        ziel_gut=formatiere(ergebnis["ziel_gut"], "zahl"),
        ziel_schwach=formatiere(ergebnis["ziel_schwach"], "zahl"),
    )
    return kontext


@login_required
def muster(request):
    ziel = request.GET.get("ziel")
    if ziel not in ZIELGROESSEN:
        ziel = "produktivitaet"
    return render(
        request, "tracking/muster.html", _muster_kontext(request.user, ziel, timezone.now())
    )


# --- Plan vs. Ist (Wochenkalender) ---------------------------------------------

PLAN_MAX_TAGE = 62


def _eintraege_im_zeitraum(nutzer, beginn, ende):
    """Einträge, die [beginn, ende) berühren (auch über die Grenze ragende, laufende)."""
    return list(
        Eintrag.objects.filter(nutzer=nutzer, start__lt=ende)
        .filter(Q(ende__isnull=True) | Q(ende__gt=beginn))
        .select_related("kategorie")
        .order_by("start")
    )


def _kalender_zeitraum(request):
    """start/end von FullCalendar (ISO 8601). Ungültig oder > 62 Tage: None."""
    try:
        von = datetime.fromisoformat(request.GET["start"])
        bis = datetime.fromisoformat(request.GET["end"])
    except (KeyError, ValueError):
        return None
    von, bis = (timezone.make_aware(x) if timezone.is_naive(x) else x for x in (von, bis))
    if bis <= von or bis - von > timedelta(days=PLAN_MAX_TAGE):
        return None
    return von, bis


def _plan_event(b):
    name = b.kategorie.name
    return {
        "id": str(b.pk),
        "title": f"{name}: {b.titel}" if b.titel else name,
        "start": b.start.isoformat(),
        "end": b.ende.isoformat(),
        "color": b.kategorie.farbe,
        "extendedProps": {"kategorie": b.kategorie_id, "titel": b.titel},
    }


def _fehler(form):
    texte = [f for liste in form.errors.values() for f in liste]
    return JsonResponse({"fehler": " ".join(texte) or "Ungültige Eingabe."}, status=400)


@login_required
def plan(request):
    if "datum" in request.GET:
        try:
            datum = date.fromisoformat(request.GET["datum"])
        except ValueError:
            datum = tagesdatum(timezone.now())
    else:
        datum = tagesdatum(timezone.now())
    kategorien = Kategorie.objects.filter(nutzer=request.user, aktiv=True)
    return render(request, "tracking/plan.html", {"datum": datum, "kategorien": kategorien})


@login_required
def plan_bloecke(request):
    zeitraum = _kalender_zeitraum(request)
    if zeitraum is None:
        return JsonResponse({"fehler": "Ungültiger Zeitraum."}, status=400)
    von, bis = zeitraum
    bloecke = _planbloecke(request.user, von, bis)
    return JsonResponse([_plan_event(b) for b in bloecke], safe=False)


@login_required
def plan_ist(request):
    zeitraum = _kalender_zeitraum(request)
    if zeitraum is None:
        return JsonResponse({"fehler": "Ungültiger Zeitraum."}, status=400)
    von, bis = zeitraum
    jetzt = timezone.now()
    events = [
        {
            "id": f"ist-{e.pk}",
            "title": e.kategorie.name,
            "start": e.start.isoformat(),
            "end": (e.ende or jetzt).isoformat(),
            "color": e.kategorie.farbe,
            "editable": False,
            "classNames": ["ist"],
        }
        for e in _eintraege_im_zeitraum(request.user, von, bis)
    ]
    return JsonResponse(events, safe=False)


@login_required
@require_POST
def plan_speichern(request, pk=None):
    block = get_object_or_404(Planblock, pk=pk, nutzer=request.user) if pk else None
    form = PlanblockForm(request.POST, instance=block, nutzer=request.user)
    if not form.is_valid():
        return _fehler(form)
    gespeichert = form.save(commit=False)
    gespeichert.nutzer = request.user
    gespeichert.save()
    return JsonResponse(_plan_event(gespeichert), status=200 if block else 201)


@login_required
@require_POST
def plan_loeschen(request, pk):
    get_object_or_404(Planblock, pk=pk, nutzer=request.user).delete()
    return JsonResponse({"ok": True})


# --- Einstellungen: API-Tokens ---------------------------------------------------


@login_required
@never_cache
def einstellungen(request):
    form = TokenForm(request.POST or None)
    neu = None
    if request.method == "POST" and form.is_valid():
        # Bewusst kein Redirect (PRG): Der Klartext existiert nur hier und darf nicht in Session
        # oder Datenbank zwischengelagert werden. Ein Neuladen legt höchstens ein weiteres Token an.
        name = form.cleaned_data["name"]
        neu = {"name": name, "klartext": ApiToken.erzeugen(request.user, name)[1]}
        form = TokenForm()
    return render(
        request,
        "tracking/einstellungen.html",
        {"form": form, "neu": neu, "tokens": ApiToken.objects.filter(nutzer=request.user)},
    )


@login_required
@require_POST
def token_widerrufen(request, pk):
    get_object_or_404(ApiToken, pk=pk, nutzer=request.user).delete()
    return redirect("einstellungen")
