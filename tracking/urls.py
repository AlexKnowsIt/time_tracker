from datetime import date

from django.contrib.auth import views as auth_views
from django.urls import path, register_converter

from . import views


class IsoDatum:
    regex = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"

    def to_python(self, value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValueError from None  # URL passt nicht -> 404

    def to_url(self, value):
        return str(value)


register_converter(IsoDatum, "datum")

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="tracking/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("", views.jetzt, name="jetzt"),
    path("start/<int:pk>/", views.start, name="start"),
    path("stopp/", views.stopp, name="stopp"),
    path("messung/", views.messung, name="messung"),
    path("tag/", views.tag, name="heute"),
    path("tag/<datum:datum>/", views.tag, name="tag"),
    path("tag/<datum:datum>/neu/", views.eintrag_form, name="eintrag_neu"),
    path("tag/<datum:datum>/abschluss/", views.abschluss, name="abschluss"),
    path("abschluss/", views.abschluss_heute, name="abschluss_heute"),
    path("woche/", views.woche, name="woche_aktuell"),
    path("woche/<datum:datum>/", views.woche, name="woche"),
    path("plan/", views.plan, name="plan"),
    path("plan/bloecke/", views.plan_bloecke, name="plan_bloecke"),
    path("plan/ist/", views.plan_ist, name="plan_ist"),
    path("plan/neu/", views.plan_speichern, name="plan_neu"),
    path("plan/<int:pk>/", views.plan_speichern, name="plan_bearbeiten"),
    path("plan/<int:pk>/loeschen/", views.plan_loeschen, name="plan_loeschen"),
    path("muster/", views.muster, name="muster"),
    path("messung/<int:pk>/loeschen/", views.messung_loeschen, name="messung_loeschen"),
    path("eintrag/<int:pk>/", views.eintrag_form, name="eintrag_bearbeiten"),
    path("eintrag/<int:pk>/loeschen/", views.eintrag_loeschen, name="eintrag_loeschen"),
]
