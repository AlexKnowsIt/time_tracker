// Diagramme (Chart.js): Zeit je Art pro Tag (Woche) und Verlauf der Bewertungen (Muster).
// Daten kommen per json_script aus der Seite; Farben aus den CSS-Tokens (Hell/Dunkel).
(function () {
  if (!window.Chart) return;
  const dunkel = window.matchMedia("(prefers-color-scheme: dark)");
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const zahl = (n, stellen) => new Intl.NumberFormat("de-DE", { maximumFractionDigits: stellen }).format(n);
  const dauer = (min) => {
    const m = Math.round(min);
    return m >= 60 ? Math.floor(m / 60) + " Std " + (m % 60 ? (m % 60) + " min" : "") : m + " min";
  };
  const datum = (iso, optionen) => new Date(iso + "T12:00:00").toLocaleDateString("de-DE", optionen);

  function grundoptionen() {
    const gitter = css("--diagramm-gitter"), text = css("--diagramm-text");
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? false : { duration: 300 },
      font: { family: css("--schrift") },
      color: text,
      scales: {
        x: { grid: { display: false }, border: { color: gitter }, ticks: { color: text } },
        y: { grid: { color: gitter }, border: { display: false }, ticks: { color: text } },
      },
      plugins: {
        tooltip: { backgroundColor: css("--flaeche"), titleColor: css("--text"), bodyColor: css("--text"), borderColor: gitter, borderWidth: 1, padding: 10, cornerRadius: 10, boxPadding: 4 },
      },
    };
  }

  function woche(daten) {
    const o = grundoptionen();
    o.scales.x.stacked = true;
    o.scales.y.stacked = true;
    o.scales.y.ticks.callback = (v) => (v % 60 === 0 ? v / 60 + " Std" : "");
    o.scales.y.ticks.stepSize = 60;
    o.plugins.legend = { position: "bottom", labels: { color: css("--diagramm-text"), usePointStyle: true, pointStyle: "rectRounded", boxWidth: 8 } };
    o.plugins.tooltip.callbacks = {
      label: (c) => " " + c.dataset.label + ": " + dauer(c.parsed.y),
      footer: (items) => "Summe: " + dauer(items.reduce((s, i) => s + i.parsed.y, 0)),
    };
    return {
      type: "bar",
      data: {
        labels: daten.tage.map((t) => datum(t, { weekday: "short" })),
        datasets: daten.arten.map((a) => ({
          label: a.label, data: a.minuten, backgroundColor: css("--art-" + a.key),
          borderColor: css("--flaeche"), borderWidth: 1, borderRadius: 4, borderSkipped: false, maxBarThickness: 40,
        })),
      },
      options: o,
    };
  }

  function verlauf(daten) {
    const o = grundoptionen();
    const p = css("--serie-produktivitaet"), z = css("--serie-zufriedenheit");
    o.scales.y.min = 0; o.scales.y.max = 10; o.scales.y.ticks.stepSize = 2;
    o.scales.x.ticks.maxTicksLimit = 6;
    o.scales.x.ticks.maxRotation = 0;
    o.plugins.legend = { position: "bottom", labels: { color: css("--diagramm-text"), boxWidth: 24, boxHeight: 3, filter: (i) => !i.text.startsWith("Tageswert") } };
    o.interaction = { mode: "index", intersect: false };
    o.plugins.tooltip.callbacks = {
      title: (items) => datum(daten.tage[items[0].dataIndex], { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric" }),
      label: (c) => " " + c.dataset.label + ": " + zahl(c.parsed.y, 1) + " von 10",
    };
    const punkte = (name, daten_, farbe) => ({ label: "Tageswert " + name, data: daten_, showLine: false, borderColor: "transparent", backgroundColor: farbe + "66", pointRadius: 2.5, pointHoverRadius: 4 });
    const linie = (name, daten_, farbe) => ({ label: name + " (Ø 7 Tage)", data: daten_, borderColor: farbe, backgroundColor: farbe, borderWidth: 3, pointRadius: 0, pointHoverRadius: 4, tension: .3, spanGaps: true });
    return {
      type: "line",
      data: {
        labels: daten.tage.map((t) => datum(t, { day: "2-digit", month: "2-digit" })),
        datasets: [
          punkte("Produktivität", daten.produktivitaet, p), punkte("Zufriedenheit", daten.zufriedenheit, z),
          linie("Produktivität", daten.schnitt_produktivitaet, p), linie("Zufriedenheit", daten.schnitt_zufriedenheit, z),
        ],
      },
      options: o,
    };
  }

  const bauer = { woche, verlauf };
  const diagramme = [];
  function zeichne() {
    diagramme.splice(0).forEach((c) => c.destroy());
    document.querySelectorAll("canvas[data-diagramm]").forEach((canvas) => {
      const quelle = document.getElementById(canvas.dataset.quelle);
      if (!quelle || !bauer[canvas.dataset.diagramm]) return;
      canvas.parentElement.hidden = false;
      diagramme.push(new Chart(canvas, bauer[canvas.dataset.diagramm](JSON.parse(quelle.textContent))));
    });
  }
  zeichne();
  dunkel.addEventListener("change", zeichne);
})();
