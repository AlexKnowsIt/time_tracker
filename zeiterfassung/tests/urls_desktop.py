"""URLconf für Tests: die normale plus der Desktop-Anmeldelink (wie im Desktop-Modus)."""

from zeiterfassung import urls

urlpatterns = urls.desktop_urlpatterns + urls.urlpatterns
