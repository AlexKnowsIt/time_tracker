# PyInstaller-Spezifikation der Windows-App (onedir, ohne Konsole).
# Vorher im Projektordner: DJANGO_SECRET_KEY=x python manage.py collectstatic --noinput
# Bauen:  uv run --group desktop pyinstaller desktop/zeiterfassung.spec --noconfirm
# Ergebnis: dist/Zeiterfassung/Zeiterfassung.exe
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

WURZEL = Path(SPECPATH).parent  # noqa: F821 (SPECPATH liefert PyInstaller)
WINDOWS = sys.platform == "win32"

datas = [
    (str(WURZEL / "staticfiles"), "staticfiles"),  # collectstatic-Ergebnis für WhiteNoise
    (str(WURZEL / "tracking" / "templates"), "tracking/templates"),
]
datas += collect_data_files("tzdata")  # Zeitzonen unter Windows


def eigene_module(paket):
    """Alle .py unter dem Paket als Modulnamen. collect_submodules scheitert hier, weil es die
    Module importiert und settings ohne Schlüssel abbricht."""
    return [
        ".".join(p.relative_to(WURZEL).with_suffix("").parts).removesuffix(".__init__")
        for p in (WURZEL / paket).rglob("*.py")
        if "tests" not in p.parts
    ]


# Per Zeichenkette geladene Module (INSTALLED_APPS, MIDDLEWARE, Migrationen) findet die
# Analyse nicht von selbst.
hiddenimports = (
    eigene_module("tracking")
    + eigene_module("zeiterfassung")
    + collect_submodules("django.contrib")
    + collect_submodules("django.middleware")
    + collect_submodules("django.db.backends.sqlite3")
    + collect_submodules("whitenoise")
    + collect_submodules("waitress")
)
binaries = []
if WINDOWS:  # pywebview: Edge-WebView2-Anbindung (Plattformmodule, DLLs, Skripte)
    hiddenimports += collect_submodules("webview.platforms")
    datas += collect_data_files("webview")
    binaries += collect_dynamic_libs("webview")

a = Analysis(  # noqa: F821
    [str(WURZEL / "desktop" / "start.py")],
    pathex=[str(WURZEL)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["mcp", "pytest", "ruff", "gunicorn", "tkinter"],
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Zeiterfassung",
    console=False,  # Fenster-Anwendung, kein Konsolenfenster
    icon=str(WURZEL / "desktop" / "zeiterfassung.ico") if WINDOWS else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Zeiterfassung")  # noqa: F821
