from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class Kategorie(models.Model):
    class Art(models.TextChoices):
        DEEPWORK = "deepwork", "Deep Work"
        SHALLOWWORK = "shallowwork", "Shallow Work"
        ORGANISATION = "organisation", "Organisation"
        PAUSE = "pause", "Pause"
        FREIZEIT = "freizeit", "Freizeit"

    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    art = models.CharField(max_length=15, choices=Art)
    farbe = models.CharField(max_length=7, default="#888888", help_text="Hex, z. B. #3366cc")
    aktiv = models.BooleanField(default=True, help_text="Alte Kategorien ausblenden statt löschen")

    class Meta:
        verbose_name_plural = "Kategorien"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Eintrag(models.Model):
    """Ein Zeitblock. ende leer = läuft gerade."""

    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kategorie = models.ForeignKey(Kategorie, on_delete=models.PROTECT)
    start = models.DateTimeField()
    ende = models.DateTimeField(null=True, blank=True)
    notiz = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Einträge"
        ordering = ["-start"]
        constraints = [
            models.UniqueConstraint(
                fields=["nutzer"],
                condition=Q(ende__isnull=True),
                name="max_ein_laufender_eintrag",
            ),
            models.CheckConstraint(
                condition=Q(ende__isnull=True) | Q(ende__gt=F("start")),
                name="ende_nach_start",
            ),
        ]

    def __str__(self):
        return f"{self.kategorie} ab {self.start:%d.%m. %H:%M}"


class Messung(models.Model):
    """Zählbare Dinge zu einem Zeitpunkt."""

    class Typ(models.TextChoices):
        WASSER_ML = "wasser_ml", "Wasser (ml)"
        KAFFEE = "kaffee", "Kaffee"

    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    zeitpunkt = models.DateTimeField()
    typ = models.CharField(max_length=20, choices=Typ)
    menge = models.PositiveIntegerField()

    class Meta:
        verbose_name_plural = "Messungen"
        ordering = ["-zeitpunkt"]

    def __str__(self):
        return f"{self.get_typ_display()}: {self.menge}"


class Tagesbewertung(models.Model):
    """Einmal pro Tag, beim Tagesabschluss."""

    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    datum = models.DateField()
    produktivitaet = models.PositiveSmallIntegerField(
        "Produktivität",
        help_text="Wie produktiv war der Tag? (1–10)",
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    zufriedenheit = models.PositiveSmallIntegerField(
        "Zufriedenheit",
        help_text="Wie zufrieden bist du mit dem Tag? (1–10)",
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    schlaf_h = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    notiz = models.TextField(blank=True, help_text="Was hat geholfen, was hat gestört?")

    class Meta:
        verbose_name_plural = "Tagesbewertungen"
        ordering = ["-datum"]
        constraints = [
            models.UniqueConstraint(fields=["nutzer", "datum"], name="eine_bewertung_pro_tag"),
            models.CheckConstraint(
                condition=Q(produktivitaet__gte=1, produktivitaet__lte=10),
                name="produktivitaet_1_bis_10",
            ),
            models.CheckConstraint(
                condition=Q(zufriedenheit__gte=1, zufriedenheit__lte=10),
                name="zufriedenheit_1_bis_10",
            ),
        ]

    def __str__(self):
        return (
            f"{self.datum}: Produktivität {self.produktivitaet}, Zufriedenheit {self.zufriedenheit}"
        )
