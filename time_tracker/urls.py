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
from django.urls import path, include
from dashboard_student.views import dashboard_data_view_st, dashboard_data_view_lt
from input_lerntag.views import create_lerntag#, zeiteinsatz_tag_view, zeiteinsatz_tag_istvssoll_view, zeiteinsatz_woche_arbeit_view, zeiteinsatz_woche_view, zeiteinsatz_monat_view, zeiteinsatz_monat_arbeit_view, zeiteinsatz_monat_combined_productivity_view, zeiteinsatz_monat_all_cat_view
from input_lerntag.views import DashboardView, TrendView
from fullcalendar.views import event_view, create_planung, CalendarView, CalendarLookView, event_detail_view

urlpatterns = [
    path('admin/', admin.site.urls),

    # Views for websites
    path('dashboard/', dashboard_data_view_st),
    path('trend/', dashboard_data_view_lt),
    path('', create_lerntag),
    path('planner/', create_planung),
    path('calendar/', event_view),

    # Calendar vies
    # path('api/calendar/<int:id>/', CalendarView.as_view()),
    path('api/calendar/<int:id>/', event_detail_view),
    path('api/calendar/', CalendarLookView.as_view()),

    # Dashboard views
    path('api/dashboard/<str:dashboard>/', DashboardView.as_view()),
    path('api/trend/<str:dashboard>/', TrendView.as_view()),
]
