"""JSON-API unter /api/v1/ (Zielbild Abschnitt 9). Plain Django, Logik aus den Seiten-Views.

Authentifizierung nur per ``Authorization: Bearer <token>``. Session-Cookies werden hier bewusst
ignoriert: ohne Cookie-Auth gibt es keinen CSRF-Angriffsweg, deshalb ist ``csrf_exempt`` sicher.

ponytail: kein Rate-Limiting. Einzelnutzer hinter Cloudflare Access; das Token ist 256 Bit lang
und nicht ratbar. Upgrade-Pfad bei mehreren Nutzern oder offenem Betrieb: Zähler pro Token und
Minute im Cache (oder ``django-ratelimit``) im Dekorator ``api`` und 429 zurückgeben.
"""

import json
from datetime import date, datetime, timedelta
from functools import wraps

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from . import experimente
from .experiment_views import (
    design_text,
    ergebnis_anzeige,
    experiment_ergebnis,
    experiment_werte,
    fortschritt,
    vorlagen_liste,
)
from .forms import BewertungForm, EintragForm, ExperimentForm, PlanblockForm
from .merkmale import MERKMALE, formatiere, tagesmerkmale
from .models import ApiToken, Experiment, Kategorie, Messung, Planblock, Tagesbewertung
from .plan import plan_vs_ist
from .services import (
    beende_abgelaufene_experimente,
    bestaetige_experimenttag,
    starte_eintrag,
    starte_experiment,
    stoppe_eintrag,
)
from .views import (
    MESSUNG_KNOEPFE,
    MUSTER_TAGE,
    PLAN_MAX_TAGE,
    ZIELGROESSEN,
    _bewertungen,
    _eintraege_im_zeitraum,
    _jetzt_kontext,
    _muster_kontext,
    _nach_tagen,
    _nachgetragen,
    _plan_faktor,
    _planbloecke,
    _sozialer_jetlag,
    _tage_mit_merkmalen,
    _woche_daten,
)
from .zeit import tagesdatum, tagesgrenzen

MAX_BODY = 10 * 1024
MAX_MENGE = 5000
LETZTE_NUTZUNG_ALLE = timedelta(minutes=1)


class ApiFehler(Exception):
    def __init__(self, status, fehler, felder=None):
        super().__init__(fehler)
        self.status, self.fehler, self.felder = status, fehler, felder or {}


def _fehler_antwort(status, fehler, felder=None, **kopfzeilen):
    antwort = JsonResponse({"fehler": fehler, "felder": felder or {}}, status=status)
    for name, wert in kopfzeilen.items():
        antwort[name.replace("_", "-")] = wert
    return antwort


def _token_nutzer(request):
    """Nutzer zum Bearer-Token oder None. Aktualisiert zuletzt_genutzt höchstens je Minute."""
    kopf = request.META.get("HTTP_AUTHORIZATION", "")
    schema, _, klartext = kopf.partition(" ")
    if schema.lower() != "bearer" or not klartext.strip():
        return None
    token = (
        ApiToken.objects.select_related("nutzer")
        .filter(token_hash=ApiToken.hash_von(klartext.strip()), nutzer__is_active=True)
        .first()
    )
    if token is None:
        return None
    jetzt = timezone.now()
    if token.zuletzt_genutzt is None or jetzt - token.zuletzt_genutzt >= LETZTE_NUTZUNG_ALLE:
        ApiToken.objects.filter(pk=token.pk).update(zuletzt_genutzt=jetzt)
    return token.nutzer


def _lese_json(request):
    roh = request.read(MAX_BODY + 1)
    if len(roh) > MAX_BODY:
        raise ApiFehler(413, f"Der Body darf höchstens {MAX_BODY // 1024} KB groß sein.")
    if not roh.strip():
        return {}
    try:
        daten = json.loads(roh)
    except ValueError:
        raise ApiFehler(400, "Der Body ist kein gültiges JSON.") from None
    if not isinstance(daten, dict):
        raise ApiFehler(400, "Der Body muss ein JSON-Objekt sein.")
    return daten


def api(*methoden):
    """Bearer-Auth, Methodenprüfung, JSON-Body (``request.json``) und einheitliche Fehler."""

    def dekorator(view):
        # csrf_exempt ist sicher: Cookies/Sessions zählen hier nie, nur der Bearer-Header.
        @csrf_exempt
        @never_cache
        @wraps(view)
        def innen(request, *args, **kwargs):
            nutzer = _token_nutzer(request)
            if nutzer is None:
                return _fehler_antwort(
                    401,
                    "Token fehlt oder ist ungültig. Header: Authorization: Bearer <token>.",
                    WWW_Authenticate="Bearer",
                )
            if request.method not in methoden:
                return _fehler_antwort(
                    405, f"Methode {request.method} nicht erlaubt.", Allow=", ".join(methoden)
                )
            request.user = nutzer
            try:
                request.json = _lese_json(request) if request.method in ("POST", "PUT") else {}
                return view(request, *args, **kwargs)
            except ApiFehler as e:
                return _fehler_antwort(e.status, e.fehler, e.felder)
            except Http404:
                return _fehler_antwort(404, "Nicht gefunden.")

        return innen

    return dekorator


# --- Hilfen ---------------------------------------------------------------------


def _zeit(z):
    return timezone.localtime(z).isoformat(timespec="seconds") if z else None


def _kat(k):
    return {"id": k.pk, "name": k.name, "art": k.art}


def _eintrag(e, jetzt):
    return {
        "id": e.pk,
        "kategorie": _kat(e.kategorie),
        "start": _zeit(e.start),
        "ende": _zeit(e.ende),
        "dauer_min": round(((e.ende or jetzt) - e.start).total_seconds() / 60),
        "laeuft": e.ende is None,
        "notiz": e.notiz,
        "abgeschlossen": e.abgeschlossen,
        "unterbrochen": e.unterbrochen,
        "nachgetragen": e.nachgetragen,
    }


def _messung(m):
    return {"id": m.pk, "zeitpunkt": _zeit(m.zeitpunkt), "typ": m.typ, "menge": m.menge}


def _bewertung(b):
    if b is None:
        return None
    return {
        "datum": str(b.datum),
        "produktivitaet": b.produktivitaet,
        "zufriedenheit": b.zufriedenheit,
        "fortschritt": b.fortschritt,
        "fortschritt_notiz": b.fortschritt_notiz,
        "abgeschaltet": b.abgeschaltet,
        "schlaf_h": float(b.schlaf_h) if b.schlaf_h is not None else None,
        "bettzeit": b.bettzeit.strftime("%H:%M") if b.bettzeit else None,
        "aufstehzeit": b.aufstehzeit.strftime("%H:%M") if b.aufstehzeit else None,
        "notiz": b.notiz,
    }


def _planblock(b):
    return {
        "id": b.pk,
        "kategorie": _kat(b.kategorie),
        "start": _zeit(b.start),
        "ende": _zeit(b.ende),
        "titel": b.titel,
    }


def _kategorie(nutzer, wert, status):
    """Eigene aktive Kategorie per id oder Name (ohne Beachtung der Groß-/Kleinschreibung)."""
    if wert is None or wert == "" or isinstance(wert, bool):
        raise ApiFehler(400, "Kategorie fehlt.", {"kategorie": ["Pflichtfeld: id oder Name."]})
    aktive = list(Kategorie.objects.filter(nutzer=nutzer, aktiv=True))
    if isinstance(wert, int) or (isinstance(wert, str) and wert.strip().isdigit()):
        treffer = [k for k in aktive if k.pk == int(wert)]
    elif isinstance(wert, str):
        # casefold in Python: SQLite vergleicht Umlaute sonst nur groß-/klein-sensitiv
        treffer = [k for k in aktive if k.name.casefold() == wert.strip().casefold()]
    else:
        raise ApiFehler(
            400, "Kategorie muss eine id oder ein Name sein.", {"kategorie": ["Ungültig."]}
        )
    if len(treffer) == 1:
        return treffer[0]
    if treffer:
        text = f"Der Name „{wert}“ ist nicht eindeutig. Bitte die id verwenden."
        raise ApiFehler(400, text, {"kategorie": [text]})
    namen = ", ".join(f"{k.name} (id {k.pk})" for k in aktive) or "keine"
    text = f"Keine aktive Kategorie „{wert}“. Vorhandene: {namen}."
    raise ApiFehler(status, text, {"kategorie": [text]})


def _formdaten(request):
    """JSON-Felder als Text für Django-Formulare; Kategorie (id oder Name) wird zur id."""
    daten = {}
    for feld, wert in request.json.items():
        if isinstance(wert, dict | list):
            text = f"Feld „{feld}“ muss Text oder Zahl sein."
            raise ApiFehler(400, text, {feld: [text]})
        if wert is not None:
            daten[feld] = str(wert)
    if "kategorie" in request.json:
        daten["kategorie"] = str(_kategorie(request.user, request.json["kategorie"], 400).pk)
    return daten


def _form_fehler(form):
    felder = {feld: list(texte) for feld, texte in form.errors.items()}
    text = " ".join(
        t if feld == "__all__" else f"{feld}: {t}" for feld, texte in felder.items() for t in texte
    )
    return ApiFehler(400, text or "Ungültige Eingabe.", felder)


def _runde(wert, stellen=2):
    return None if wert is None else round(wert, stellen)


def _zeitgrenze(text, name, ende):
    """ISO-Datum (ganzer Tag, 04:00-Grenzen) oder ISO-Zeit; naive Zeiten in TIME_ZONE."""
    text = (text or "").strip()
    if not text:
        raise ApiFehler(400, f"Parameter „{name}“ fehlt.", {name: ["Pflichtfeld."]})
    try:
        if len(text) == 10:
            return tagesgrenzen(date.fromisoformat(text))[1 if ende else 0]
        zeit = datetime.fromisoformat(text)
    except ValueError:
        msg = f"„{name}“ ist kein ISO-8601-Datum oder -Zeitpunkt."
        raise ApiFehler(400, msg, {name: [msg]}) from None
    return timezone.make_aware(zeit) if timezone.is_naive(zeit) else zeit


# --- Endpunkte ------------------------------------------------------------------


@api("GET")
def jetzt(request):
    jetzt_ = timezone.now()
    k = _jetzt_kontext(request.user)
    return JsonResponse(
        {
            "laufend": _eintrag(k["laufend"], jetzt_) if k["laufend"] else None,
            "kategorien": [_kat(c) for c in k["kategorien"]],
            "heute": {
                "datum": str(tagesdatum(jetzt_)),
                "wasser_ml": k["wasser_ml"],
                "kaffee": k["kaffee"],
            },
        }
    )


@api("POST")
def start(request):
    kategorie = _kategorie(request.user, request.json.get("kategorie"), 404)
    eintrag = starte_eintrag(request.user, kategorie)
    return JsonResponse({"eintrag": _eintrag(eintrag, timezone.now())}, status=201)


@api("POST")
def stopp(request):
    eintrag = stoppe_eintrag(request.user)
    if eintrag is None:
        return JsonResponse({"eintrag": None, "hinweis": "Es lief kein Eintrag."})
    return JsonResponse({"eintrag": _eintrag(eintrag, timezone.now())})


@api("POST")
def messung(request):
    typ = request.json.get("typ")
    if typ not in MESSUNG_KNOEPFE:
        text = f"typ muss einer von {', '.join(MESSUNG_KNOEPFE)} sein."
        raise ApiFehler(400, text, {"typ": [text]})
    menge = request.json.get("menge")
    if menge is None:
        menge = MESSUNG_KNOEPFE[typ]
    if isinstance(menge, bool) or not isinstance(menge, int) or not 1 <= menge <= MAX_MENGE:
        text = f"menge muss eine ganze Zahl von 1 bis {MAX_MENGE} sein."
        raise ApiFehler(400, text, {"menge": [text]})
    m = Messung.objects.create(nutzer=request.user, zeitpunkt=timezone.now(), typ=typ, menge=menge)
    k = _jetzt_kontext(request.user)
    return JsonResponse(
        {"messung": _messung(m), "heute": {"wasser_ml": k["wasser_ml"], "kaffee": k["kaffee"]}},
        status=201,
    )


@api("POST")
def eintraege(request):
    form = EintragForm(_formdaten(request), nutzer=request.user)
    if not form.is_valid():
        raise _form_fehler(form)
    eintrag = form.save(commit=False)
    eintrag.nutzer = request.user
    eintrag.save()
    return JsonResponse({"eintrag": _eintrag(eintrag, timezone.now())}, status=201)


@api("GET")
def tag(request, datum):
    jetzt_ = timezone.now()
    beginn, ende = tagesgrenzen(datum)
    eintraege_ = _nach_tagen(request.user, datum, datum)
    tag_eintraege, tag_messungen = eintraege_[0].get(datum, []), eintraege_[1].get(datum, [])
    bewertung = Tagesbewertung.objects.filter(nutzer=request.user, datum=datum).first()
    planbloecke = _planbloecke(request.user, beginn, ende)
    plan_ist = None
    if planbloecke:
        ist = _eintraege_im_zeitraum(request.user, beginn, ende)
        plan_ist = plan_vs_ist(planbloecke, ist, beginn, ende, jetzt_)
    merkmale = None
    if bewertung:  # Score vor Statistik: Tagesmerkmale erst nach der Bewertung
        werte = tagesmerkmale(tag_eintraege, tag_messungen, jetzt_)
        merkmale = [
            {"key": key, "label": label, "wert": werte[key], "anzeige": formatiere(werte[key], f)}
            for key, label, f in MERKMALE
            if werte.get(key) is not None
        ]
    return JsonResponse(
        {
            "datum": str(datum),
            "eintraege": [_eintrag(e, jetzt_) for e in tag_eintraege],
            "messungen": [_messung(m) for m in tag_messungen],
            "bewertung": _bewertung(bewertung),
            "plan_ist": plan_ist,
            "merkmale": merkmale,
            "hinweis": None if bewertung else "Merkmale erscheinen erst nach der Tagesbewertung.",
        }
    )


@api("POST")
def bewertung(request, datum):
    vorhanden = Tagesbewertung.objects.filter(nutzer=request.user, datum=datum).first()
    form = BewertungForm(_formdaten(request), instance=vorhanden)
    if not form.is_valid():
        raise _form_fehler(form)
    gespeichert = form.save(commit=False)
    gespeichert.nutzer, gespeichert.datum = request.user, datum
    gespeichert.save()
    return JsonResponse({"bewertung": _bewertung(gespeichert)}, status=200 if vorhanden else 201)


@api("GET")
def woche(request, datum):
    montag, sonntag, tage = _woche_daten(request.user, datum, timezone.now())
    return JsonResponse(
        {
            "von": str(montag),
            "bis": str(sonntag),
            "tage": [
                {
                    "datum": str(t["datum"]),
                    "bewertet": t["bewertung"] is not None,
                    "produktivitaet": t["bewertung"].produktivitaet if t["bewertung"] else None,
                    "zufriedenheit": t["bewertung"].zufriedenheit if t["bewertung"] else None,
                    "deepwork_min": round(t["deepwork_min"])
                    if t["deepwork_min"] is not None
                    else None,
                }
                for t in tage
            ],
        }
    )


@api("GET")
def muster(request):
    ziel = request.GET.get("ziel", "produktivitaet")
    if ziel not in ZIELGROESSEN:
        text = f"ziel muss einer von {', '.join(ZIELGROESSEN)} sein."
        raise ApiFehler(400, text, {"ziel": [text]})
    k = _muster_kontext(request.user, ziel, timezone.now())
    antwort = {
        "ziel": ziel,
        "min_tage": k["min_tage"],
        "tage_max": k["tage_max"],
        "sozialer_jetlag_min": _runde(k["sozialer_jetlag"], 0),
        "anteil_nachgetragen": _runde(k["anteil_nachgetragen"]),
    }
    if k["nachgetragen_hinweis"]:
        antwort["nachgetragen_hinweis"] = (
            "Mehr als die Hälfte der Einträge ist nachgetragen, also rekonstruiert "
            "(Kahneman et al. 2004): Merkmale wie Pausen und Wechsel sind dann ungenauer."
        )
    if "fehlend" in k:
        antwort.update(
            bewertete_tage=k["bewertet"],
            fehlend=k["fehlend"],
            hinweis=f"Noch {k['fehlend']} bewertete Tage bis zur ersten Auswertung.",
        )
        return JsonResponse(antwort)
    e = k["ergebnis"]
    antwort.update(
        bewertete_tage=e["n"],
        gruppe_n=e["gruppe_n"],
        ziel_gut=e["ziel_gut"],
        ziel_schwach=e["ziel_schwach"],
        zeilen=[
            {
                "key": z["key"],
                "label": z["label"],
                "gut": z["gut_text"],
                "schwach": z["schwach_text"],
                "effekt": round(z["effekt"], 2),
                "delta": _runde(z["delta"]),
                "ki": [_runde(z["ki_unten"]), _runde(z["ki_oben"])],
                "deutlich": z["deutlich"],
            }
            for z in e["zeilen"]
        ],
        hinweis="Gute gegen schwache Tage (oberes gegen unteres Drittel, sortiert nach Cliff's "
        "Delta, Intervall per Block-Bootstrap): Unterschiede, keine Ursachen. Nur als "
        "Hypothesen verstehen; Ursachen prüft man mit Experimenten.",
    )
    korr = k.get("korr")
    if korr is None:
        antwort["korrelationen"] = {
            "fehlend": k["korr_fehlend"],
            "hinweis": f"Korrelationen erst ab {k['min_tage_korrelation']} bewerteten Tagen.",
        }
    else:
        antwort["korrelationen"] = {
            "lag1_zielgroesse": _runde(korr["lag1"]),
            "effektives_n": round(korr["n_eff"]),
            "zeilen": [
                {
                    "key": z["key"],
                    "label": z["label"],
                    "n": z["n"],
                    "r": _runde(z["r"]),
                    "ki": [_runde(z["ki_unten"]), _runde(z["ki_oben"])],
                    "p": _runde(z["p"], 3),
                    "hypothese": z["hypothese"],
                    "bh_treffer": z["bh_treffer"],
                }
                for z in korr["zeilen"]
            ],
            "hinweis": "Spearman-Korrelation nach Abzug der Wochentagsmittel, Intervall per "
            "Block-Bootstrap, p per Permutation, Mehrfachtest nach Benjamini-Hochberg (q=0,1). "
            "Als Hypothese gilt nur |r| >= 0,3. Zusammenhänge, keine Ursachen.",
        }
    modell = k.get("modell")
    if modell is None:
        antwort["mehrfachmodell"] = {
            "fehlend": k["modell_fehlend"],
            "hinweis": f"Mehrfachmodell erst ab {k['min_tage_modell']} bewerteten Tagen.",
        }
    else:
        antwort["mehrfachmodell"] = {
            "n_merkmale": modell["n_merkmale"],
            "koeffizienten": [
                {"key": c["key"], "label": c["label"], "koeffizient": _runde(c["koeff"])}
                for c in modell["koeffizienten"]
            ],
            "hinweis": "Ridge-Regression, standardisiert, rein explorativ (kein Train/Test-Split). "
            "Zeigt, welche Merkmale bei gleichzeitiger Betrachtung zusammenhängen, keine Ursachen.",
        }
    return JsonResponse(antwort)


@api("GET", "POST")
def plan(request):
    if request.method == "POST":
        form = PlanblockForm(_formdaten(request), nutzer=request.user)
        if not form.is_valid():
            raise _form_fehler(form)
        block = form.save(commit=False)
        block.nutzer = request.user
        block.save()
        return JsonResponse({"planblock": _planblock(block)}, status=201)
    von = _zeitgrenze(request.GET.get("start"), "start", ende=False)
    bis = _zeitgrenze(request.GET.get("ende"), "ende", ende=True)
    if bis <= von or bis - von > timedelta(days=PLAN_MAX_TAGE):
        text = f"ende muss nach start liegen, höchstens {PLAN_MAX_TAGE} Tage Abstand."
        raise ApiFehler(400, text, {"ende": [text]})
    bloecke = _planbloecke(request.user, von, bis)
    return JsonResponse(
        {
            "planbloecke": [_planblock(b) for b in bloecke],
            "plan_faktor": [
                {
                    "art": f["art"],
                    "label": f["label"],
                    "faktor": round(f["faktor"], 2),
                    "tage": f["tage"],
                    "text": f"{f['label']}: du schaffst im Median {f['prozent']} % des Plans "
                    f"({f['tage']} Tage mit Plan). Plane entsprechend mehr Zeit ein.",
                }
                for f in _plan_faktor(request.user, timezone.now())
            ],
        }
    )


@api("DELETE")
def plan_loeschen(request, pk):
    get_object_or_404(Planblock, pk=pk, nutzer=request.user).delete()
    return JsonResponse({"ok": True})


# --- Selbstexperimente -----------------------------------------------------------------


def _experiment_json(e, heute):
    tage = list(e.tage.all())
    heute_tag = next((t for t in tage if t.datum == heute), None)
    antworten = [t for t in tage if t.datum <= heute and t.eingehalten is not None]
    return {
        "id": e.pk,
        "titel": e.titel,
        "hypothese": e.hypothese,
        "regel": e.regel_satz,
        "bedingung_a": e.bedingung_a,
        "design": e.design,
        "design_text": design_text(e.design, e.blocklaenge, e.dauer_tage),
        "zielgroesse": e.zielgroesse,
        "ziel_label": experimente.ZIELE[e.zielgroesse][0],
        "start": str(e.start),
        "ende": str(e.ende),
        "status": e.status,
        "abbruch_vermerk": e.abbruch_vermerk,
        "fortschritt": fortschritt(e, heute),
        "heute": {
            "datum": str(heute),
            "bedingung": heute_tag.bedingung,
            "vorgabe": e.regel_satz if heute_tag.bedingung == "B" else e.bedingung_a,
            "eingehalten": heute_tag.eingehalten,
        }
        if heute_tag
        else None,
        "einhaltung": {
            "antworten": len(antworten),
            "ja": sum(1 for t in antworten if t.eingehalten),
        },
        # Zuweisung steht vorab fest; Ergebnisse folgen erst nach dem Ende (siehe "beendete")
        "tage": [
            {"datum": str(t.datum), "bedingung": t.bedingung, "eingehalten": t.eingehalten}
            for t in tage
        ],
    }


def _ergebnis_json(erg):
    a = erg
    return {
        "aussage": a["aussage"],
        "text": a["text"],
        "tage_a": a["n_a"],
        "tage_b": a["n_b"],
        "median_a": _runde(a["median_a"]),
        "median_b": _runde(a["median_b"]),
        "differenz_b_minus_a": _runde(a["differenz"]),
        "p": _runde(a["p"], 3),
        "verfahren": a["verfahren"],
        "cliffs_delta": _runde(a["delta"]),
        "delta_ki": [_runde(a["delta_ki"][0]), _runde(a["delta_ki"][1])],
        "einhaltung_b_prozent": a["einhaltung_b_prozent"],
        "nur_eingehaltene_tage": a["protokoll_text"],
    }


@api("GET", "POST")
def experiment(request):
    jetzt_ = timezone.now()
    heute = tagesdatum(jetzt_)
    beende_abgelaufene_experimente(request.user, heute)
    if request.method == "POST":
        return _experiment_starten(request, heute)
    alle = list(Experiment.objects.filter(nutzer=request.user).prefetch_related("tage"))
    laufend = next((e for e in alle if e.status == Experiment.Status.LAEUFT), None)
    beendete = [e for e in alle if e.status == Experiment.Status.BEENDET]
    werte = experiment_werte(request.user, beendete, jetzt_)
    return JsonResponse(
        {
            "laufend": _experiment_json(laufend, heute) if laufend else None,
            "beendete": [
                {
                    "id": e.pk,
                    "titel": e.titel,
                    "regel": e.regel_satz,
                    "ziel_label": experimente.ZIELE[e.zielgroesse][0],
                    "ergebnis": _ergebnis_json(
                        ergebnis_anzeige(experiment_ergebnis(e, werte[e.pk]), e.zielgroesse)
                    ),
                }
                for e in beendete
            ],
            "vorlagen": [
                {k: v[k] for k in ("key", "titel", "regel", "design_text", "ziel_label", "hinweis")}
                for v in vorlagen_liste()
            ],
            "hinweis": "Ergebnisse erscheinen erst nach dem Ende des Experiments; die Zuordnung "
            "zu A oder B steht vorab fest. Starten: POST mit vorlage oder eigenen Feldern.",
        }
    )


def _experiment_starten(request, heute):
    daten = {}
    vorlage_key = request.json.get("vorlage")
    if vorlage_key:
        v = experimente.VORLAGEN.get(vorlage_key)
        if v is None:
            text = f"Unbekannte Vorlage. Möglich: {', '.join(experimente.VORLAGEN)}."
            raise ApiFehler(400, text, {"vorlage": [text]})
        daten = {
            "titel": v["titel"],
            "hypothese": v["hypothese"],
            "regel_wenn": v["wenn"],
            "regel_dann": v["dann"],
            "design": v["design"],
            "blocklaenge": v["blocklaenge"],
            "dauer_tage": v["dauer"],
            "zielgroesse": v["ziel"],
        }
    daten["start"] = str(heute)
    for feld, wert in request.json.items():
        if feld == "vorlage" or wert is None:
            continue
        if isinstance(wert, dict | list):
            text = f"Feld „{feld}“ muss Text oder Zahl sein."
            raise ApiFehler(400, text, {feld: [text]})
        daten[feld] = str(wert)
    form = ExperimentForm(daten, nutzer=request.user)
    if not form.is_valid():
        raise _form_fehler(form)
    c = form.cleaned_data
    try:
        e = starte_experiment(
            request.user,
            **{
                k: c[k]
                for k in (
                    "titel",
                    "hypothese",
                    "regel_wenn",
                    "regel_dann",
                    "bedingung_a",
                    "design",
                    "blocklaenge",
                    "dauer_tage",
                    "zielgroesse",
                    "start",
                )
            },
        )
    except ValueError as fehler:
        raise ApiFehler(409, str(fehler)) from None
    return JsonResponse({"experiment": _experiment_json(e, heute)}, status=201)


@api("POST")
def experiment_tag(request, datum):
    eingehalten = request.json.get("eingehalten")
    if not isinstance(eingehalten, bool):
        text = "eingehalten muss true oder false sein."
        raise ApiFehler(400, text, {"eingehalten": [text]})
    tag = bestaetige_experimenttag(request.user, datum, eingehalten)
    if tag is None:
        raise ApiFehler(404, "An diesem Datum gibt es keinen Experimenttag.")
    return JsonResponse(
        {"datum": str(tag.datum), "bedingung": tag.bedingung, "eingehalten": tag.eingehalten}
    )


WOCHE_MERKMALE = (
    "deepwork_min",
    "erfasst_min",
    "beginn",
    "ende",
    "laengster_deepwork_min",
    "wechsel_pro_h",
    "pausen_anzahl",
    "pausen_min",
    "wasser_ml",
    "letzter_kaffee",
    "anteil_nachgetragen",
)
WOCHE_VERGLEICH_TAGE = 28


def _muster_kompakt(nutzer, ziel, jetzt):
    """Die wichtigsten Muster-Hinweise einer Zielgröße für den Wochenbericht."""
    k = _muster_kontext(nutzer, ziel, jetzt)
    if "fehlend" in k:
        return {
            "ziel": ziel,
            "hinweis": f"Noch {k['fehlend']} bewertete Tage bis zur ersten Auswertung.",
        }
    e = k["ergebnis"]
    korr = k.get("korr")
    return {
        "ziel": ziel,
        "bewertete_tage": e["n"],
        "gute_gegen_schwache_tage": [
            {
                "merkmal": z["label"],
                "gute_tage": z["gut_text"],
                "schwache_tage": z["schwach_text"],
                "delta": _runde(z["delta"]),
                "deutlich": z["deutlich"],
            }
            for z in e["zeilen"][:4]
        ],
        "korrelationen": [
            {"merkmal": z["label"], "r": _runde(z["r"]), "fdr_fest": z["bh_treffer"], "n": z["n"]}
            for z in (korr["zeilen"] if korr else [])
            if z["hypothese"]
        ][:4],
    }


@api("GET")
def wochenbericht(request, datum):
    """Alles, was ein Sprachmodell für einen vorsichtigen Wochenrückblick braucht, kompakt."""
    jetzt_ = timezone.now()
    heute = tagesdatum(jetzt_)
    beende_abgelaufene_experimente(request.user, heute)
    montag, sonntag, tage = _woche_daten(request.user, datum, jetzt_)
    bewertete = [t["datum"] for t in tage if t["bewertung"]]
    merkmale = {}
    if bewertete:
        bewertungen = _bewertungen(request.user, montag, sonntag)
        for b, m in _tage_mit_merkmalen(request.user, bewertete, bewertungen, jetzt_):
            merkmale[b["datum"]] = {
                k: formatiere(m[k], f)
                for k, _, f in MERKMALE
                if k in WOCHE_MERKMALE and m.get(k) is not None
            }
    davor = Tagesbewertung.objects.filter(
        nutzer=request.user,
        datum__range=(montag - timedelta(days=WOCHE_VERGLEICH_TAGE), montag - timedelta(days=1)),
    )

    def schnitt(werte):
        werte = list(werte)
        return round(sum(werte) / len(werte), 1) if werte else None

    experiment_ = (
        Experiment.objects.filter(nutzer=request.user, status=Experiment.Status.LAEUFT)
        .prefetch_related("tage")
        .first()
    )
    woche_tage = []
    for t in tage:
        b = t["bewertung"]
        woche_tage.append(
            {
                "datum": str(t["datum"]),
                "wochentag": t["datum"].strftime("%A"),
                "bewertet": b is not None,
                **(
                    {
                        "produktivitaet": b.produktivitaet,
                        "zufriedenheit": b.zufriedenheit,
                        "fortschritt": b.fortschritt,
                        "fortschritt_notiz": b.fortschritt_notiz,
                        "abgeschaltet": b.abgeschaltet,
                        "schlaf_h": float(b.schlaf_h) if b.schlaf_h is not None else None,
                        "notiz": b.notiz,
                        "merkmale": merkmale.get(t["datum"], {}),
                    }
                    if b
                    else {}
                ),
            }
        )
    muster = [_muster_kompakt(request.user, z, jetzt_) for z in ("produktivitaet", "zufriedenheit")]
    nachgetragen = _nachgetragen(request.user, heute - timedelta(days=MUSTER_TAGE - 1), heute)
    return JsonResponse(
        {
            "woche": {"von": str(montag), "bis": str(sonntag), "tage": woche_tage},
            "vergleich_vorherige_4_wochen": {
                "produktivitaet_schnitt": schnitt(b.produktivitaet for b in davor),
                "zufriedenheit_schnitt": schnitt(b.zufriedenheit for b in davor),
                "bewertete_tage": len(davor),
            },
            "muster_hinweise": muster,
            "plan_faktor": [
                {"art": f["label"], "prozent_des_plans_im_median": f["prozent"], "tage": f["tage"]}
                for f in _plan_faktor(request.user, jetzt_)
            ],
            "sozialer_jetlag_min": _runde(_sozialer_jetlag(request.user, heute), 0),
            "anteil_nachgetragen": _runde(nachgetragen["anteil_nachgetragen"]),
            "laufendes_experiment": _experiment_json(experiment_, heute) if experiment_ else None,
            "experiment_vorlagen": [
                {k: v[k] for k in ("key", "titel", "regel", "design_text", "ziel_label", "hinweis")}
                for v in vorlagen_liste()
            ],
            "hinweis": "Muster sind Unterschiede und Zusammenhänge, keine Ursachen. Nur die "
            "Experimente können kausale Hinweise liefern.",
        }
    )


@csrf_exempt
def unbekannt(request, rest):
    return _fehler_antwort(404, "Unbekannter Endpunkt.")
