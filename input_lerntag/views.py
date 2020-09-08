from django.shortcuts import render
from django.http import JsonResponse
from .models import Lerntag
from .forms import LerntagForm

# Create your views here.
def create_lerntag(request):
    my_form = LerntagForm(request.POST or None)
    if my_form.is_valid():
        my_form.save()
    context = {
        'form': my_form
    }
    return render(request, 'input.html', context)

# 2 oder 3 Seiten --> täglich, wöchentlich, Trend

# täglich

# Kuchendiagramm mit rel. und absoluten Werten für alle Kategorien
def zeiteinsatz_tag_view(request):
    Lerntage = Lerntag.objects.all()
    label = ['Deepwork', 'Shallow Work', 'Freizeit', 'Organisation']
    day = Lerntage[len(Lerntage)-1]
    daten = [day.zeit_arbeit_mental, day.zeit_arbeit_shallow, day.zeit_freizeit, day.zeit_organisation]
    # for day in Lerntage:
    #     Datume.append(day.datum)
    #     Werte.append(float(day.zeit_arbeit_mental))
    daten = {
        'labels': label,
        'daten': daten
    }
    return JsonResponse(daten)

# Barchart Ist Soll
def zeiteinsatz_tag_istvssoll_view(request):
    Lerntage = Lerntag.objects.all()
    label = ['Deepwork', 'Shallow Work', 'Freizeit', 'Organisation']
    day = Lerntage[len(Lerntage)-1]
    daten = [day.zeit_arbeit_mental, day.zeit_arbeit_shallow, day.zeit_freizeit, day.zeit_organisation]
    # for day in Lerntage:
    #     Datume.append(day.datum)
    #     Werte.append(float(day.zeit_arbeit_mental))
    daten = {
        'labels': label,
        'daten': daten
    }
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
