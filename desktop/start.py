"""Einstiegspunkt der Windows-App (Desktop-Modus).

Ablauf: Daten unter %LOCALAPPDATA%\\Zeiterfassung, migrate, waitress auf 127.0.0.1 und freiem Port,
Fenster per pywebview (Edge WebView2). Das Fenster öffnet einen Anmelde-Link mit einmaligem
Geheimnis (siehe zeiterfassung/desktop.py). Fenster schließen beendet den Server.

Lokal ohne Fenster: `uv run --group desktop python desktop/start.py --nur-server`
"""

import argparse
import os
import secrets
import sys
import threading
from pathlib import Path


def datenverzeichnis():
    if os.environ.get("ZEITERFASSUNG_DATEN"):  # zum Testen und für portable Installationen
        return Path(os.environ["ZEITERFASSUNG_DATEN"])
    if os.name == "nt":
        return Path(os.environ["LOCALAPPDATA"]) / "Zeiterfassung"
    return Path.home() / ".local" / "share" / "zeiterfassung"  # nur für Entwicklung unter Linux


def main(argv=None):
    parser = argparse.ArgumentParser(description="Zeiterfassung als Desktop-App")
    parser.add_argument("--nur-server", action="store_true", help="ohne Fenster, Link ausgeben")
    parser.add_argument("--url-datei", help="Anmelde-Link zusätzlich in diese Datei schreiben")
    args = parser.parse_args(argv)

    if not getattr(sys, "frozen", False):  # aus dem Quellbaum gestartet: Projektordner importierbar
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    daten = datenverzeichnis()
    daten.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None or sys.stderr is None:  # PyInstaller --windowed: keine Konsole
        log = open(daten / "zeiterfassung.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log

    os.environ["ZEITERFASSUNG_MODUS"] = "desktop"
    os.environ["DJANGO_DB_PATH"] = str(daten / "db.sqlite3")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zeiterfassung.settings")

    import django
    from django.conf import settings
    from django.core.management import call_command

    django.setup()
    call_command("migrate", interactive=False, verbosity=0)
    if not (Path(settings.STATIC_ROOT) / "staticfiles.json").exists():
        # Entwicklung ohne vorheriges collectstatic; die gebaute App bringt die Dateien mit
        call_command("collectstatic", interactive=False, verbosity=0)

    from waitress import create_server

    from zeiterfassung import desktop
    from zeiterfassung.wsgi import application

    server = create_server(application, listen="127.0.0.1:0", threads=4)
    port = server.effective_port
    geheimnis = secrets.token_urlsafe(32)
    desktop.geheimnis_registrieren(geheimnis)
    link = f"http://127.0.0.1:{port}/desktop-anmeldung/{geheimnis}/"
    threading.Thread(target=server.run, daemon=True).start()

    try:
        if args.nur_server:
            print(f"Zeiterfassung läuft: http://127.0.0.1:{port}/\nAnmelde-Link (einmalig): {link}")
            sys.stdout.flush()
            if args.url_datei:
                Path(args.url_datei).write_text(link, encoding="utf-8")
            threading.Event().wait()  # bis Strg+C oder Prozessende
        else:
            import webview

            webview.create_window(
                "Zeiterfassung", link, width=1100, height=800, min_size=(380, 600)
            )
            webview.start()  # kehrt zurück, wenn das Fenster geschlossen wird
    except KeyboardInterrupt:
        pass
    finally:
        server.close()


if __name__ == "__main__":
    main()
