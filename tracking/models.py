from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class Kategorie(models.Model):
    class Art(models.TextChoices):
        FOKUS = "fokus", "Fokus"
        ROUTINE = "routine", "Routine"
        PAUSE = "pause", "Pause"
        PRIVAT = "privat", "Privat"

    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    art = models.CharField(max_length=10, choices=Art)
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
    score = models.PositiveSmallIntegerField(
        "Score",
        help_text="Wie produktiv hat sich der Tag angefühlt? (1–10)",
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    energie = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1–5",
    )
    schlaf_h = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    notiz = models.TextField(blank=True, help_text="Was hat geholfen, was hat gestört?")

    class Meta:
        verbose_name_plural = "Tagesbewertungen"
        ordering = ["-datum"]
        constraints = [
            models.UniqueConstraint(fields=["nutzer", "datum"], name="eine_bewertung_pro_tag"),
            models.CheckConstraint(condition=Q(score__gte=1, score__lte=10), name="score_1_bis_10"),
            models.CheckConstraint(
                condition=Q(energie__isnull=True) | Q(energie__gte=1, energie__lte=5),
                name="energie_1_bis_5",
            ),
        ]

    def __str__(self):
        return f"{self.datum}: {self.score}"
