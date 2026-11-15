"""Erzeugt die PNG/ICO-Symbole aus dem Motiv von tracking/static/tracking/icon.svg.

Einmalig von Hand nötig, das Ergebnis liegt im Repo:
    uv run --with pillow python desktop/icons_erzeugen.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

WURZEL = Path(__file__).resolve().parent.parent
BLAU, WEISS = (31, 78, 140, 255), (255, 255, 255, 255)
SCHARF = 4  # Supersampling gegen Treppenkanten


def symbol(groesse):
    """Quadratisches Symbol im Maßstab der 64er-Vorlage."""
    g = groesse * SCHARF
    k = g / 64
    bild = Image.new("RGBA", (g, g), (0, 0, 0, 0))
    d = ImageDraw.Draw(bild)
    d.rounded_rectangle((0, 0, g - 1, g - 1), radius=14 * k, fill=BLAU)
    d.ellipse(
        (32 * k - 20.5 * k, 32 * k - 20.5 * k, 32 * k + 20.5 * k, 32 * k + 20.5 * k),
        outline=WEISS,
        width=round(5 * k),
    )
    zeiger = [(32 * k, 21 * k), (32 * k, 33 * k), (40 * k, 38 * k)]
    d.line(zeiger, fill=WEISS, width=round(5 * k), joint="curve")
    for x, y in (zeiger[0], zeiger[-1]):  # runde Enden
        r = 2.5 * k
        d.ellipse((x - r, y - r, x + r, y + r), fill=WEISS)
    return bild.resize((groesse, groesse), Image.LANCZOS)


def logo(breite, hoehe):
    """Symbol links, Schriftzug fehlt bewusst (kein Font im Repo): Symbol zentriert auf Blau."""
    bild = Image.new("RGBA", (breite, hoehe), BLAU)
    s = symbol(hoehe - 16)
    bild.alpha_composite(s, ((breite - s.width) // 2, 8))
    return bild


if __name__ == "__main__":
    ha = WURZEL / "homeassistant" / "zeiterfassung"
    symbol(128).save(ha / "icon.png")
    logo(250, 100).save(ha / "logo.png")
    symbol(256).save(
        WURZEL / "desktop" / "zeiterfassung.ico",
        sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)],
    )
