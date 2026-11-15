"""Selbstexperimente: Vorlagen, Zuweisung und Auswertung. Reine Funktionen ohne DB-Zugriff.

Grundlage: docs/forschung.md (Kratochwill & Levin 2010; Daskalova et al. 2017; Gollwitzer &
Sheeran 2006). Die Bedingung jedes Tages wird beim Start vorab zufällig zugewiesen, die
Auswertung ist ein Randomisierungstest unter genau diesem Schema. Alles ist über ein
übergebenes ``random.Random`` deterministisch.
"""

import random
import statistics

from . import statistik

TAGEWEISE, BLOECKE, ABAB = "tageweise", "bloecke", "abab"
MIN_TAGE, MAX_TAGE = 8, 120
HYPOTHESE_P = 0.05  # „spricht dafür“ ab hier, „Hinweis“ bis zum Doppelten
N_PERM = 5000
N_BOOT = 1000

# Zielgrößen: Schlüssel -> (Label, Format, Quelle).
# bewertung = Feld der Tagesbewertung desselben Tages, folgenacht = Schlaf der Nacht nach dem
# Tag (steht in der Bewertung des Folgetags), merkmal = Tagesmerkmal, plan = Ist/Plan des Tages.
ZIELE = {
    "produktivitaet": ("Produktivität (1–10)", "zahl", "bewertung"),
    "zufriedenheit": ("Zufriedenheit (1–10)", "zahl", "bewertung"),
    "abgeschaltet": ("Abschalten (1–5)", "zahl", "bewertung"),
    "schlaf_folgenacht": ("Schlaf der folgenden Nacht (Stunden)", "zahl", "folgenacht"),
    "deepwork_min": ("Deep Work gesamt", "dauer", "merkmal"),
    "wechsel_pro_h": ("Kategoriewechsel pro Arbeitsstunde", "zahl", "merkmal"),
    "beginn": ("Arbeitsbeginn", "uhrzeit", "merkmal"),
    "plan_erfuellung": ("Erfasst im Verhältnis zum Plan", "prozent", "plan"),
}

# Die acht Vorlagen aus docs/forschung.md. hinweis = Evidenz und Quelle in einem Satz.
VORLAGEN = {
    "koffein_schluss": {
        "titel": "Koffein-Schluss",
        "hypothese": "Wenn ich nach 14 Uhr keinen Kaffee mehr trinke, schlafe ich länger.",
        "wenn": "es 14 Uhr ist",
        "dann": "trinke ich keinen Kaffee mehr",
        "design": BLOECKE,
        "blocklaenge": 2,
        "dauer": 16,
        "ziel": "schlaf_folgenacht",
        "hinweis": "Evidenz mittel (kleine Studie, hohe Dosis): Drake et al. 2013.",
    },
    "schlafkorridor": {
        "titel": "Schlafkorridor",
        "hypothese": "Wenn ich um 22:30 Uhr ins Bett gehe, bin ich am nächsten Tag produktiver.",
        "wenn": "es 22:30 Uhr ist",
        "dann": "gehe ich ins Bett",
        "design": ABAB,
        "blocklaenge": 14,
        "dauer": 56,
        "ziel": "produktivitaet",
        "hinweis": "Evidenz stark für die Wirkung von Schlafmangel: Van Dongen et al. 2003.",
    },
    "mikropausen": {
        "titel": "Mikropausen",
        "hypothese": "Mit Mikropausen bin ich abends zufriedener.",
        "wenn": "ich 50 Minuten gearbeitet habe",
        "dann": "mache ich 5–10 Minuten Pause",
        "design": TAGEWEISE,
        "blocklaenge": 1,
        "dauer": 20,
        "ziel": "zufriedenheit",
        "hinweis": "Evidenz mittel für Energie, schwach für Leistung: Albulescu et al. 2022.",
    },
    "gebuendelte_kommunikation": {
        "titel": "Gebündelte Kommunikation",
        "hypothese": "Ohne Mails und Chat im Deep Work wechsle ich seltener die Tätigkeit.",
        "wenn": "ich vormittags Deep Work mache",
        "dann": "öffne ich keine Mails und keinen Chat",
        "design": TAGEWEISE,
        "blocklaenge": 1,
        "dauer": 20,
        "ziel": "wechsel_pro_h",
        "hinweis": "Evidenz mittel (Attention Residue): Leroy 2009; Mark et al. 2008.",
    },
    "abschlussnotiz": {
        "titel": "Abschlussnotiz",
        "hypothese": "Mit einer kurzen Notiz beim Wechsel fühle ich mich produktiver.",
        "wenn": "ich einen Block wechsle",
        "dann": "notiere ich 2 Minuten lang Stand und nächsten Schritt",
        "design": TAGEWEISE,
        "blocklaenge": 1,
        "dauer": 20,
        "ziel": "produktivitaet",
        "hinweis": "Evidenz mittel (Attention Residue): Leroy 2009.",
    },
    "wenn_dann_start": {
        "titel": "Wenn-dann-Start",
        "hypothese": "Mit einer festen Startregel schaffe ich mehr Deep Work.",
        "wenn": "ich morgens am Schreibtisch sitze",
        "dann": "beginne ich sofort mit dem geplanten Deep-Work-Block",
        "design": TAGEWEISE,
        "blocklaenge": 1,
        "dauer": 28,
        "ziel": "deepwork_min",
        "hinweis": "Evidenz mittel, kleiner als früher berichtet: Gollwitzer & Sheeran 2006.",
    },
    "plan_puffer": {
        "titel": "Plan-Puffer",
        "hypothese": "Mit Puffer im Plan erreiche ich einen größeren Teil dessen, was ich plane.",
        "wenn": "ich plane",
        "dann": "multipliziere ich die Dauer mit meinem Plan-Faktor",
        "design": ABAB,
        "blocklaenge": 7,
        "dauer": 28,
        "ziel": "plan_erfuellung",
        "hinweis": "Evidenz stark für den Planungsfehler: Buehler, Griffin & Ross 1994.",
    },
    "abschalt_ritual": {
        "titel": "Abschalt-Ritual",
        "hypothese": "Mit einem festen Feierabendritual bin ich abends zufriedener.",
        "wenn": "ich Feierabend mache",
        "dann": "schließe ich mit einem festen Ritual ab",
        "design": ABAB,
        "blocklaenge": 7,
        "dauer": 28,
        "ziel": "zufriedenheit",
        "hinweis": "Evidenz mittel (korrelativ): Wendsche & Lohmann-Haislah 2017.",
    },
}


def design_fehler(design, dauer_tage, blocklaenge):
    """Fehlertext, wenn das Design nicht zur Dauer passt, sonst None (ein Ort für Form und API)."""
    if dauer_tage is None or blocklaenge is None:
        return "Dauer fehlt."
    if not MIN_TAGE <= dauer_tage <= MAX_TAGE:
        return f"Die Dauer muss zwischen {MIN_TAGE} und {MAX_TAGE} Tagen liegen."
    if design == TAGEWEISE:
        return None
    if design == BLOECKE:
        if not 2 <= blocklaenge <= 14:
            return "Ein Block hat 2 bis 14 Tage."
        if dauer_tage % blocklaenge:
            return f"Die Dauer muss ein Vielfaches der Blocklänge ({blocklaenge} Tage) sein."
        if dauer_tage // blocklaenge < 4:
            return "Mit weniger als 4 Blöcken lässt sich nichts auswerten."
        return None
    if design == ABAB:
        if not 2 <= blocklaenge <= 28:
            return "Eine ABAB-Phase hat 2 bis 28 Tage."
        if dauer_tage != 4 * blocklaenge:
            return f"ABAB hat vier Phasen: Dauer = 4 × Phasenlänge = {4 * blocklaenge} Tage."
        return None
    return "Unbekanntes Design."


def zuweisung(design, dauer_tage, blocklaenge, rng):
    """Bedingung ("A"/"B") je Tag. tageweise: balanciert (gleich viele, bei ungerader Zahl
    zufällig eines mehr); Blöcke: ganze Blöcke balanciert; ABAB: feste Phasen, Start A oder B."""
    fehler = design_fehler(design, dauer_tage, blocklaenge)
    if fehler:
        raise ValueError(fehler)
    laenge = 1 if design == TAGEWEISE else blocklaenge
    m = dauer_tage // laenge
    if design == ABAB:
        einheiten = ["B", "A"] * (m // 2) if rng.random() < 0.5 else ["A", "B"] * (m // 2)
    else:
        k_b = m // 2 + (m % 2 and rng.random() < 0.5)
        gewaehlt = set(rng.sample(range(m), k_b))
        einheiten = ["B" if i in gewaehlt else "A" for i in range(m)]
    return [e for e in einheiten for _ in range(laenge)]


def diff_text(wert, format):
    """Differenz mit Vorzeichen; Uhrzeiten und Dauern in Minuten, Anteile in Prozentpunkten."""
    if wert is None:
        return "–"
    if format in ("dauer", "uhrzeit"):
        text = f"{abs(wert):.0f} min"
    elif format == "prozent":
        text = f"{abs(wert) * 100:.0f} Prozentpunkte"
    else:
        text = f"{abs(wert):.1f}".replace(".", ",")
    return ("+" if wert > 1e-9 else "−" if wert < -1e-9 else "±") + text


def _gruppe(tage, bedingung, nur_treue=False):
    return [
        t[1]
        for t in tage
        if t[0] == bedingung and t[1] is not None and not (nur_treue and t[2] is False)
    ]


def auswerten(tage, design, blocklaenge, zielgroesse, rng=None):
    """Ergebnis eines Experiments. ``tage``: [(bedingung, wert|None, eingehalten|None)] in
    zeitlicher Reihenfolge, genau so, wie vorab zugewiesen.

    Primär nach Zuweisung (Intention-to-treat): alle Tage zählen nach der zugewiesenen
    Bedingung, egal ob die Regel eingehalten wurde. Nebenergebnis: ohne Tage, an denen
    „nicht eingehalten“ angegeben wurde, nur beschreibend (ohne p), weil das Ausschließen die
    Zufallszuweisung bricht. Einhaltung: Anteil „ja“ unter den beantworteten Tagen je Bedingung.
    """
    rng = rng or random.Random(0)
    format = ZIELE[zielgroesse][1] if zielgroesse in ZIELE else "zahl"
    bedingungen = [t[0] for t in tage]
    a, b = _gruppe(tage, "A"), _gruppe(tage, "B")
    test = statistik.randomisierungstest(
        [t[1] for t in tage], bedingungen, design, blocklaenge, n_perm=N_PERM, rng=rng
    )
    delta, ki_unten, ki_oben = statistik.delta_mit_ki(b, a, N_BOOT, rng)

    def einhaltung(bedingung):
        antworten = [t[2] for t in tage if t[0] == bedingung and t[2] is not None]
        return (sum(antworten) / len(antworten) if antworten else None), len(antworten)

    treu_a, treu_b = _gruppe(tage, "A", True), _gruppe(tage, "B", True)
    protokoll = None
    if min(len(treu_a), len(treu_b)) >= statistik.MIN_JE_BEDINGUNG:
        protokoll = {
            "n_a": len(treu_a),
            "n_b": len(treu_b),
            "differenz": statistics.median(treu_b) - statistics.median(treu_a),
            "delta": statistik.cliffs_delta(treu_b, treu_a),
        }
    einhaltung_a, n_a = einhaltung("A")
    einhaltung_b, n_b = einhaltung("B")
    ergebnis = {
        "format": format,
        "n_a": len(a),
        "n_b": len(b),
        "median_a": statistics.median(a) if a else None,
        "median_b": statistics.median(b) if b else None,
        "differenz": None if test is None else test["beobachtet"],
        "p": None if test is None else test["p"],
        "exakt": None if test is None else test["exakt"],
        "n_zuweisungen": None if test is None else test["n_zuweisungen"],
        "p_min": None if test is None else test["p_min"],
        "delta": delta,
        "delta_ki": (ki_unten, ki_oben),
        "einhaltung_a": einhaltung_a,
        "einhaltung_a_n": n_a,
        "einhaltung_b": einhaltung_b,
        "einhaltung_b_n": n_b,
        "nicht_eingehalten": sum(1 for t in tage if t[2] is False),
        "protokoll": protokoll,
    }
    ergebnis["aussage"] = _aussage(ergebnis)
    ergebnis["text"] = ergebnis_text(ergebnis, zielgroesse)
    return ergebnis


def _aussage(e):
    """dafuer | hinweis | unklar | zu_wenig | nicht_pruefbar."""
    if e["p"] is None:
        return "zu_wenig"
    if e["p_min"] > HYPOTHESE_P:
        return "nicht_pruefbar"
    ki_unten, ki_oben = e["delta_ki"]
    ki_ohne_null = ki_unten is not None and (ki_unten > 0 or ki_oben < 0)
    if e["p"] <= HYPOTHESE_P and ki_ohne_null:
        return "dafuer"
    if e["p"] <= 2 * HYPOTHESE_P:
        return "hinweis"
    return "unklar"


def _zahl3(p):
    return f"{p:.3f}".replace(".", ",")


def ergebnis_text(e, zielgroesse):
    """Vorsichtiger Satz zum Ergebnis: Hypothese, nie Beweis oder Ursache."""
    label, format, _ = ZIELE.get(zielgroesse, (zielgroesse, "zahl", ""))
    aussage = e["aussage"]
    if aussage == "zu_wenig":
        return (
            f"Zu wenige Tage mit Wert für „{label}“ (mindestens {statistik.MIN_JE_BEDINGUNG} je "
            f"Bedingung nötig, vorhanden: A {e['n_a']}, B {e['n_b']}). Keine Auswertung möglich."
        )
    diff = diff_text(e["differenz"], format)
    richtung = "höher" if e["differenz"] > 0 else "niedriger"
    p = "p < 0,001" if e["p"] < 0.001 else f"p = {_zahl3(e['p'])}"
    zahlen = f"Median B minus A: {diff}, {p}"
    if aussage == "nicht_pruefbar":
        return (
            f"Der Randomisierungstest kann hier nichts bestätigen: Es gibt nur "
            f"{e['n_zuweisungen']} mögliche Zuweisungen, der kleinste erreichbare p-Wert ist "
            f"{_zahl3(e['p_min'])}. Beschreibend lag „{label}“ an B-Tagen im Median {richtung} "
            f"({diff}); ein Beleg ist das nicht."
        )
    if aussage == "dafuer":
        return (
            f"Spricht dafür, dass „{label}“ an B-Tagen {richtung} lag ({zahlen}). Das ist ein "
            "Hinweis aus einem einzelnen, kleinen Selbstexperiment, kein Beweis. Eine "
            "Wiederholung festigt ihn."
        )
    if aussage == "hinweis":
        return (
            f"Ein Hinweis, dass „{label}“ an B-Tagen {richtung} lag, aber unsicher ({zahlen}). "
            "Mit mehr Tagen oder einer Wiederholung wäre mehr zu sagen."
        )
    return (
        f"Kein klarer Unterschied bei „{label}“ ({zahlen}). Das heißt nicht, dass es keinen "
        "gibt: Mit so wenigen Tagen bleiben kleine Effekte unsichtbar."
    )
