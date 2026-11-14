from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import BewertungForm, EintragForm
from .models import Eintrag, Kategorie, Messung, Tagesbewertung
from .services import starte_eintrag, stoppe_eintrag
from .zeit import tagesdatum, tagesgrenzen

# Messungs-Knöpfe: Typ -> Menge pro Tipp
MESSUNG_KNOEPFE = {Messung.Typ.WASSER_ML: 250, Messung.Typ.KAFFEE: 1}


def dauer_text(sekunden):
    minuten = int(sekunden // 60)
    return f"{minuten // 60} h {minuten % 60:02d} min" if minuten >= 60 else f"{minuten} min"


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
