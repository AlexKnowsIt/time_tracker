from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.

def dashboard_data_view_st(request):
    return render (request, 'dashboard.html')

def dashboard_data_view_lt(request):
    return render (request, 'dashboard.html')
# 2 oder 3 Seiten --> täglich, wöchentlich, Trend

# täglich

# Kuchendiagramm mit rel. und absoluten Werten für alle Kategorien
def zeiteinsatz_tag_view(request): 
    pass

# Barchart Ist Soll
def zeiteinsatz_tag_istvssoll_view(request):
    pass


# wöchentlich

# Liniendiagramm Arbeit (DW SW) im Zeitverlauf
def zeiteinsatz_woche_arbeit_view(request):
    pass

# Kuchendiagramm mit rel. und absoluten Werten für alle Kategorien
def zeiteinsatz_woche_view(request):
    pass


# Trend

# letzte 30 Tage Arbeit vs 30 Tage davor
def zeiteinsatz_monat_arbeit_view(request):
    pass

# Zeiteinsatz über Monat als Kuchendiagramm
def zeiteinsatz_monat_view(request):
    pass

# Produktivität, Wohlbefinden und Deepwork Zeit
def zeiteinsatz_monat_combined_productivity_view(request):
    pass

# Liniendiagramm alle Kategorien über Monat
def zeiteinsatz_monat_all_cat_view(request):
    pass
