// Wochenkalender für „Plan vs. Ist“. Der Server validiert alles; hier nur Bedienung.
(function () {
  const el = document.getElementById("kalender");
  if (!el || !window.FullCalendar) return;
  const d = el.dataset;
  const dialog = document.getElementById("plan-dialog");
  const form = document.getElementById("plan-form");
  const feld = { kat: form.querySelector("#plan-kategorie"), titel: form.querySelector("#plan-titel") };
  const fehler = document.getElementById("plan-fehler");
  const meldung = document.getElementById("plan-meldung");
  const loeschen = document.getElementById("plan-loeschen");
  let aktuell = null; // {event} beim Bearbeiten, {start, ende} beim Anlegen

  const urlFuer = (vorlage, id) => vorlage.replace("/0/", "/" + id + "/");
  const zeitText = (s, e) =>
    s.toLocaleString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) +
    " – " + e.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });

  function zeigeMeldung(text) {
    meldung.textContent = text || "";
    meldung.hidden = !text;
  }

  async function senden(url, daten) {
    const antwort = await fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": d.csrf, "Accept": "application/json" },
      body: new URLSearchParams(daten),
      credentials: "same-origin",
    });
    let json = {};
    try { json = await antwort.json(); } catch (e) { /* keine JSON-Antwort */ }
    if (!antwort.ok) throw new Error(json.fehler || "Speichern fehlgeschlagen (" + antwort.status + ").");
    return json;
  }

  const felder = (kategorie, titel, start, ende) => ({
    kategorie, titel, start: start.toISOString(), ende: ende.toISOString(),
  });

  const kalender = new FullCalendar.Calendar(el, {
    locale: "de",
    firstDay: 1,
    initialDate: d.datum,
    initialView: window.innerWidth < 700 ? "timeGridDay" : "timeGridWeek",
    windowResize: () => kalender.changeView(window.innerWidth < 700 ? "timeGridDay" : "timeGridWeek"),
    headerToolbar: { left: "prev,next today", center: "title", right: "timeGridWeek,timeGridDay" },
    buttonText: { today: "Heute", week: "Woche", day: "Tag" },
    allDaySlot: false,
    slotMinTime: "05:00:00",
    slotMaxTime: "24:00:00",
    nowIndicator: true,
    height: "auto",
    selectable: true,
    selectMirror: true,
    selectLongPressDelay: 400,
    editable: true,
    eventLongPressDelay: 400,
    eventSources: [
      { url: d.urlIst, editable: false },
      { url: d.urlBloecke },
    ],
    eventSourceFailure: () => zeigeMeldung("Kalenderdaten konnten nicht geladen werden."),
    select(info) {
      aktuell = { start: info.start, ende: info.end };
      oeffne("Planblock anlegen", info.start, info.end, null);
    },
    eventClick(info) {
      if (info.event.classNames.includes("ist")) return;
      aktuell = { event: info.event };
      const p = info.event.extendedProps;
      oeffne("Planblock bearbeiten", info.event.start, info.event.end, p);
    },
    async eventDrop(info) { await verschieben(info); },
    async eventResize(info) { await verschieben(info); },
  });

  async function verschieben(info) {
    const e = info.event, p = e.extendedProps;
    zeigeMeldung("");
    try {
      await senden(urlFuer(d.urlBlock, e.id), felder(p.kategorie, p.titel, e.start, e.end));
    } catch (fehlerObjekt) {
      info.revert();
      zeigeMeldung(fehlerObjekt.message);
    }
  }

  function oeffne(titel, start, ende, props) {
    document.getElementById("plan-dialog-titel").textContent = titel;
    document.getElementById("plan-zeit").textContent = zeitText(start, ende);
    if (props) {
      feld.kat.value = props.kategorie;
      feld.titel.value = props.titel || "";
    } else {
      feld.titel.value = "";
    }
    loeschen.hidden = !props;
    fehler.hidden = true;
    dialog.showModal();
    feld.kat.focus();
  }

  function schliesse() {
    dialog.close();
    kalender.unselect();
    aktuell = null;
  }

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!aktuell) return;
    const e = aktuell.event;
    const start = e ? e.start : aktuell.start, ende = e ? e.end : aktuell.ende;
    const url = e ? urlFuer(d.urlBlock, e.id) : d.urlNeu;
    try {
      await senden(url, felder(feld.kat.value, feld.titel.value, start, ende));
      zeigeMeldung("");
      schliesse();
      kalender.refetchEvents();
    } catch (fehlerObjekt) {
      fehler.textContent = fehlerObjekt.message;
      fehler.hidden = false;
    }
  });

  loeschen.addEventListener("click", async () => {
    if (!aktuell || !aktuell.event) return;
    if (!confirm("Planblock löschen?")) return;
    try {
      await senden(urlFuer(d.urlLoeschen, aktuell.event.id), {});
      schliesse();
      kalender.refetchEvents();
    } catch (fehlerObjekt) {
      fehler.textContent = fehlerObjekt.message;
      fehler.hidden = false;
    }
  });

  document.getElementById("plan-abbrechen").addEventListener("click", schliesse);
  dialog.addEventListener("cancel", () => { kalender.unselect(); aktuell = null; });

  kalender.render();
})();
