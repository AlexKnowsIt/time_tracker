import hashlib
import secrets
from datetime import timedelta

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
    abgeschlossen = models.BooleanField(
        "Aufgabe abgeschlossen?", null=True, blank=True, help_text="Leer = nicht beantwortet"
    )
    unterbrochen = models.BooleanField("Unterbrochen", default=False)
    nachgetragen = models.BooleanField(
        "Nachgetragen",
        default=False,
        help_text="Per Nachtragen-Formular oder API angelegt, nicht per Timer: rekonstruiert",
    )

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
    fortschritt = models.BooleanField(
        "Fortschritt",
        null=True,  # null nur für Altdaten vor der Frage; das Formular verlangt Ja oder Nein
        blank=True,
        help_text="Hast du heute bei etwas Wichtigem Fortschritt gemacht?",
    )
    fortschritt_notiz = models.CharField("Fortschritt: Was?", max_length=200, blank=True)
    abgeschaltet = models.PositiveSmallIntegerField(
        "Abschalten",
        null=True,
        blank=True,
        help_text="Wie gut konntest du nach der Arbeit abschalten? (1–5)",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    schlaf_h = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    bettzeit = models.TimeField(null=True, blank=True, help_text="Letzte Nacht ins Bett gegangen")
    aufstehzeit = models.TimeField(null=True, blank=True, help_text="Heute aufgestanden")
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
            models.CheckConstraint(
                condition=Q(abgeschaltet__isnull=True)
                | Q(abgeschaltet__gte=1, abgeschaltet__lte=5),
                name="abgeschaltet_1_bis_5",
            ),
        ]

    def __str__(self):
        return (
            f"{self.datum}: Produktivität {self.produktivitaet}, Zufriedenheit {self.zufriedenheit}"
        )


class Planblock(models.Model):
    """Geplanter Zeitblock (Soll) für „Plan vs. Ist“. Überschneidungsfrei pro Nutzer."""

    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kategorie = models.ForeignKey(Kategorie, on_delete=models.PROTECT)
    start = models.DateTimeField()
    ende = models.DateTimeField()
    titel = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name_plural = "Planblöcke"
        ordering = ["start"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ende__gt=F("start")), name="planblock_ende_nach_start"
            ),
        ]

    def __str__(self):
        return f"Plan {self.kategorie} ab {self.start:%d.%m. %H:%M}"


class ApiToken(models.Model):
    """Persönliches Token für die JSON-API (und damit den MCP-Server).

    Gespeichert wird nur der SHA-256-Hash. Das Token ist zufällig und lang (256 Bit), daher
    reicht ein schneller Hash ohne Salt; die Suche per Hash ist zugleich der Vergleich.
    """

    PRAEFIX = "zt_"

    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, help_text="Wofür das Token gedacht ist")
    token_hash = models.CharField(max_length=64, unique=True)
    erstellt = models.DateTimeField(auto_now_add=True)
    zuletzt_genutzt = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "API-Tokens"
        ordering = ["-erstellt"]

    def __str__(self):
        return self.name

    @staticmethod
    def hash_von(klartext):
        return hashlib.sha256(klartext.encode()).hexdigest()

    @classmethod
    def erzeugen(cls, nutzer, name):
        """Legt ein Token an und gibt (ApiToken, Klartext) zurück. Der Klartext ist nur hier da."""
        klartext = cls.PRAEFIX + secrets.token_urlsafe(32)
        token = cls.objects.create(nutzer=nutzer, name=name, token_hash=cls.hash_von(klartext))
        return token, klartext


class Experiment(models.Model):
    """Selbstexperiment (Zielbild Stufe 4, docs/forschung.md). Die Zuweisung der Bedingungen
    entsteht beim Start vorab (``ExperimentTag``). Nach dem Start sind alle Felder außer
    ``status`` und ``abbruch_vermerk`` schreibgeschützt, damit niemand die Hypothese oder die
    Zielgröße nachträglich dem Ergebnis anpasst (Daskalova et al. 2017)."""

    class Design(models.TextChoices):
        TAGEWEISE = "tageweise", "Tageweise zufällig"
        BLOECKE = "bloecke", "Blöcke zufällig"
        ABAB = "abab", "ABAB (feste Phasen)"

    class Status(models.TextChoices):
        LAEUFT = "laeuft", "Läuft"
        BEENDET = "beendet", "Beendet"
        ABGEBROCHEN = "abgebrochen", "Abgebrochen"

    GESCHUETZT = (
        "nutzer_id",
        "titel",
        "hypothese",
        "regel_wenn",
        "regel_dann",
        "bedingung_a",
        "bedingung_b",
        "design",
        "blocklaenge",
        "zielgroesse",
        "start",
        "dauer_tage",
        "seed",
    )

    nutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    titel = models.CharField(max_length=100)
    hypothese = models.TextField(help_text="Was erwartest du? Vor dem Start festlegen.")
    regel_wenn = models.CharField("Wenn", max_length=200)
    regel_dann = models.CharField("Dann", max_length=200)
    bedingung_a = models.CharField(max_length=200, default="Wie immer")
    bedingung_b = models.CharField(max_length=420, blank=True, help_text="Leer = Wenn-dann-Regel")
    design = models.CharField(max_length=10, choices=Design)
    blocklaenge = models.PositiveSmallIntegerField(
        default=1, help_text="Tage je Block (Blöcke) bzw. je Phase (ABAB)"
    )
    zielgroesse = models.CharField(max_length=30)
    start = models.DateField()
    dauer_tage = models.PositiveSmallIntegerField()
    seed = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status, default=Status.LAEUFT)
    abbruch_vermerk = models.TextField(blank=True)
    erstellt = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Experimente"
        ordering = ["-start", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["nutzer"],
                condition=Q(status="laeuft"),
                name="max_ein_laufendes_experiment",
            ),
        ]

    def __str__(self):
        return self.titel

    def save(self, *args, **kwargs):
        if not self._state.adding:
            alt = Experiment.objects.filter(pk=self.pk).values(*self.GESCHUETZT).first()
            if alt and any(alt[f] != getattr(self, f) for f in self.GESCHUETZT):
                raise ValueError("Ein gestartetes Experiment lässt sich nicht mehr ändern.")
        elif not self.bedingung_b:
            self.bedingung_b = f"Wenn {self.regel_wenn}, dann {self.regel_dann}."
        super().save(*args, **kwargs)

    @property
    def regel_satz(self):
        return self.bedingung_b or f"Wenn {self.regel_wenn}, dann {self.regel_dann}."

    @property
    def ende(self):
        return self.start + timedelta(days=self.dauer_tage - 1)


class ExperimentTag(models.Model):
    """Zugewiesene Bedingung eines Tages. Datum und Bedingung sind nach dem Anlegen fest
    (der Randomisierungstest braucht genau diese Zuweisung); nur ``eingehalten`` ändert sich."""

    class Bedingung(models.TextChoices):
        A = "A", "A (wie immer)"
        B = "B", "B (Regel)"

    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name="tage")
    datum = models.DateField()
    bedingung = models.CharField(max_length=1, choices=Bedingung)
    eingehalten = models.BooleanField(null=True, blank=True, help_text="Leer = nicht beantwortet")

    class Meta:
        verbose_name_plural = "Experimenttage"
        ordering = ["datum"]
        constraints = [
            models.UniqueConstraint(fields=["experiment", "datum"], name="ein_tag_je_experiment"),
        ]

    def __str__(self):
        return f"{self.datum}: {self.bedingung}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            alt = ExperimentTag.objects.filter(pk=self.pk).values("datum", "bedingung").first()
            if alt and (alt["datum"], alt["bedingung"]) != (self.datum, self.bedingung):
                raise ValueError("Die Zuweisung eines Experimenttags ist unveränderlich.")
        super().save(*args, **kwargs)
