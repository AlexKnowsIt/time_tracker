from django.contrib import admin

from .models import Eintrag, Kategorie, Messung, Tagesbewertung


@admin.register(Kategorie)
class KategorieAdmin(admin.ModelAdmin):
    list_display = ["name", "art", "farbe", "aktiv", "nutzer"]
    list_filter = ["art", "aktiv", "nutzer"]
    search_fields = ["name"]


@admin.register(Eintrag)
class EintragAdmin(admin.ModelAdmin):
    list_display = ["kategorie", "start", "ende", "nutzer"]
    list_filter = ["nutzer", "kategorie__art", "kategorie"]
    date_hierarchy = "start"


@admin.register(Messung)
class MessungAdmin(admin.ModelAdmin):
    list_display = ["typ", "menge", "zeitpunkt", "nutzer"]
    list_filter = ["typ", "nutzer"]
    date_hierarchy = "zeitpunkt"


@admin.register(Tagesbewertung)
class TagesbewertungAdmin(admin.ModelAdmin):
    list_display = ["datum", "score", "energie", "schlaf_h", "nutzer"]
    list_filter = ["nutzer"]
    date_hierarchy = "datum"
