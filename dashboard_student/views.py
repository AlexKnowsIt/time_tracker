from django.shortcuts import render
from django.http import JsonResponse

# Create your views here.

# st = short-term
def dashboard_data_view_st(request):
    return render (request, 'dashboard_st.html')

# lt = long-term
def dashboard_data_view_lt(request):
    return render (request, 'dashboard_lt.html')

# 2 oder 3 Seiten --> täglich, wöchentlich, Trend

# täglich

# Kuchendiagramm mit rel. und absoluten Werten für alle Kategorien
def zeiteinsatz_tag_view(request):
    daten = {
        'labels': ['heute', 'gestern', 'vorgestern', 'Luki B-day'],
        'daten': [1,2,3,35]
    }
    return JsonResponse(daten)

# Barchart Ist Soll
def zeiteinsatz_tag_istvssoll_view(request):
    daten = {}
    return JsonResponse(daten)


# wöchentlich

# Liniendiagramm Arbeit (DW SW) im Zeitverlauf
def zeiteinsatz_woche_arbeit_view(request):
    daten = {}
    return JsonResponse(daten)

# Kuchendiagramm mit rel. und absoluten Werten für alle Kategorien
def zeiteinsatz_woche_view(request):
    daten = {}
    return JsonResponse(daten)


# Trend

# letzte 30 Tage Arbeit vs 30 Tage davor
def zeiteinsatz_monat_arbeit_view(request):
    daten = {}
    return JsonResponse(daten)

# Zeiteinsatz über Monat als Kuchendiagramm
def zeiteinsatz_monat_view(request):
    daten = {}
    return JsonResponse(daten)

# Produktivität, Wohlbefinden und Deepwork Zeit
def zeiteinsatz_monat_combined_productivity_view(request):
    daten = {}
    return JsonResponse(daten)

# Liniendiagramm alle Kategorien über Monat
def zeiteinsatz_monat_all_cat_view(request):
    daten = {}
    return JsonResponse(daten)
