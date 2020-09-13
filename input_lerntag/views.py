from django.shortcuts import render
from django.http import JsonResponse, HttpResponseRedirect
from .models import Lerntag
from .forms import LerntagForm
from datetime import datetime, timedelta, date

# Create your views here.
def create_lerntag(request):
    my_form = LerntagForm(request.POST or None)
    if my_form.is_valid():
        my_form.save()
        return HttpResponseRedirect('')
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
    daten = {
        'labels': label,
        'daten': daten
    }
    return JsonResponse(daten)


# wöchentlich

# Liniendiagramm Arbeit (DW SW) im Zeitverlauf
def zeiteinsatz_woche_arbeit_view(request):
    end_date = datetime.today()
    start_date = end_date - timedelta (days=7)
    Lerntage = Lerntag.objects.filter(datum__range=(start_date, end_date))
    mentale_arbeit = []
    leichte_arbeit = []
    datum = []
    for day in Lerntage:
        mentale_arbeit.append(float(day.zeit_arbeit_mental))
        leichte_arbeit.append(float(day.zeit_arbeit_shallow))
        datum.append(day.datum)
    daten = {
        'labels': datum,
        'daten': mentale_arbeit,
        'zweiteDaten': leichte_arbeit
    }
    return JsonResponse(daten)

# Kuchendiagramm mit rel. und absoluten Werten für alle Kategorien
def zeiteinsatz_woche_view(request):
    end_date = datetime.today()
    start_date = end_date - timedelta (days=7)
    Lerntage = Lerntag.objects.filter(datum__range=(start_date, end_date))    
    label = ['Deepwork', 'Shallow Work', 'Freizeit', 'Organisation']
    mentale_arbeit = 0
    leichte_arbeit = 0
    freizeit = 0
    organisation = 0
    for day in Lerntage:
        mentale_arbeit += float(day.zeit_arbeit_mental)
        leichte_arbeit += float(day.zeit_arbeit_shallow)
        freizeit += float(day.zeit_freizeit)
        organisation += float(day.zeit_organisation)
    daten = {
        'labels': label,
        'daten': [mentale_arbeit, leichte_arbeit, freizeit, organisation]
    }
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
