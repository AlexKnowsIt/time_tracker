"""time_tracker URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from dashboard_student.views import dashboard_data_view_st, dashboard_data_view_lt
from input_lerntag.views import create_lerntag, zeiteinsatz_tag_view, zeiteinsatz_tag_istvssoll_view, zeiteinsatz_woche_arbeit_view, zeiteinsatz_woche_view, zeiteinsatz_monat_view, zeiteinsatz_monat_arbeit_view, zeiteinsatz_monat_combined_productivity_view, zeiteinsatz_monat_all_cat_view
from fullcalendar.views import event_view, calendar_view
urlpatterns = [
    path('admin/', admin.site.urls),
    path('dashboard-st/', dashboard_data_view_st),
    path('dashboard-lt/', dashboard_data_view_lt),
    path('', create_lerntag),
    path('calendar/', event_view),
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
    # Calendar
    path('api/calendar/', calendar_view)
]
