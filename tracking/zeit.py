"""Zeitlogik: Tagesgrenze 04:00 Uhr in der Projekt-Zeitzone (settings.TIME_ZONE)."""

from datetime import date, datetime, time, timedelta

from django.utils import timezone

TAGESGRENZE = timedelta(hours=4)


def tagesdatum(zeitpunkt: datetime) -> date:
    """Zu welchem Tag zählt der Zeitpunkt? Vor 04:00 Uhr lokal zählt er zum Vortag."""
    return (timezone.localtime(zeitpunkt) - TAGESGRENZE).date()


def tagesgrenzen(datum: date) -> tuple[datetime, datetime]:
    """Beginn (inklusive) und Ende (exklusive) des Tages: 04:00 bis 04:00 am Folgetag."""
    beginn = timezone.make_aware(datetime.combine(datum, time(4)))
    ende = timezone.make_aware(datetime.combine(datum + timedelta(days=1), time(4)))
    return beginn, ende
