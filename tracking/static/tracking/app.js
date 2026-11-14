// Laufender Timer: zählt jede Sekunde hoch. Der Server liefert den Stand in data-sekunden;
// nach jedem HTMX-Austausch (Polling, Start, Stopp) beginnt es mit dem neuen Wert von vorn.
(function () {
  const zweistellig = (n) => String(n).padStart(2, "0");
  function tick() {
    document.querySelectorAll("[data-sekunden]").forEach((el) => {
      if (!el.dataset.gesehen) el.dataset.gesehen = String(Date.now());
      const s = Math.max(0, Math.floor(Number(el.dataset.sekunden) + (Date.now() - Number(el.dataset.gesehen)) / 1000));
      el.textContent = Math.floor(s / 3600) + ":" + zweistellig(Math.floor((s % 3600) / 60)) + ":" + zweistellig(s % 60);
    });
  }
  setInterval(tick, 1000);
  document.addEventListener("DOMContentLoaded", tick);
})();
