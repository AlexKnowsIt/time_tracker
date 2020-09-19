from .views_old import zeiteinsatz_tag_view, zeiteinsatz_tag_istvssoll_view, zeiteinsatz_woche_arbeit_view, zeiteinsatz_woche_view, zeiteinsatz_monat_arbeit_view, zeiteinsatz_monat_view, zeiteinsatz_monat_combined_productivity_view, zeiteinsatz_monat_all_cat_view
from django.urls import path

urlpatterns = [
    # APIs
    # daily
    path('api/day/', zeiteinsatz_tag_view),
    path('api/day-comp/', zeiteinsatz_tag_istvssoll_view),
    # weekly
    path('api/week-work/', zeiteinsatz_woche_arbeit_view),
    path('api/week/', zeiteinsatz_woche_view),
    # Trends
    path('api/month-work/', zeiteinsatz_monat_arbeit_view),
    path('api/month/', zeiteinsatz_monat_view),
    path('api/month-summary/', zeiteinsatz_monat_combined_productivity_view),
    path('api/month-progress/', zeiteinsatz_monat_all_cat_view),
]
