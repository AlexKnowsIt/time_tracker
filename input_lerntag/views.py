from django.shortcuts import render
from django.http import JsonResponse, HttpResponseRedirect
from .models import Lerntag
from fullcalendar.models import Events
from .forms import LerntagForm
from datetime import datetime, timedelta
from datetime import date as Datum

# Create your views here.
def create_lerntag(request):
    my_form = LerntagForm(request.POST or None)
    if my_form.is_valid():
        my_form.save()
        return HttpResponseRedirect('')
    context = {
        'form': my_form
    }
    return render(request, 'input_tracker.html', context)

# 2 oder 3 Seiten --> täglich, wöchentlich, Trend

# täglich (gestern)

# Kuchendiagramm mit rel. und absoluten Werten für alle Kategorien
def zeiteinsatz_tag_view(request):
    end_date = datetime.today()
    start_date = end_date
    Lerntage = Lerntag.objects.filter(datum__range=(start_date, end_date))    
    label = ['Deepwork', 'Shallow Work', 'Freizeit', 'Organisation']
    arbeit_mental = 0
    arbeit_shallow = 0
    freizeit = 0
    organisation = 0
    for day in Lerntage:
        arbeit_mental += day.zeit_arbeit_mental
        arbeit_shallow += day.zeit_arbeit_shallow
        freizeit += day.zeit_freizeit
        organisation += day.zeit_organisation
    daten = [arbeit_mental, arbeit_shallow, freizeit, organisation]
    daten = {
        'labels': label,
        'daten': daten
    }
    return JsonResponse(daten)

# Barchart Ist Soll
def zeiteinsatz_tag_istvssoll_view(request):
    # Lerntage = Lerntag.objects.filter(datum__date=datetime.today())
    end_date = Datum.today()
    start_date = end_date
    Lerntage = Lerntag.objects.filter(datum__range=(start_date, end_date))
    Event = Events.objects.filter(start_date__date=datetime.today())
    label = ['Deepwork', 'Shallow Work', 'Freizeit', 'Organisation']
    arbeit_mental_ist = 0
    arbeit_shallow_ist = 0
    freizeit_ist = 0
    organisation_ist = 0
    for day in Lerntage:
        arbeit_mental_ist += day.zeit_arbeit_mental
        arbeit_shallow_ist += day.zeit_arbeit_shallow
        freizeit_ist += day.zeit_freizeit
        organisation_ist += day.zeit_organisation
    zeit_ist = [float(arbeit_mental_ist), float(arbeit_shallow_ist), float(freizeit_ist), float(organisation_ist)]
    arbeit_mental_soll = 0
    arbeit_shallow_soll = 0
    freizeit_soll = 0
    organisation_soll = 0
    for eve in Event:
        time_delta = eve.end_date - eve.start_date
        duration_sec = time_delta.total_seconds()
        duration_hour = (duration_sec/3600)
        if eve.event_type == 'DW':
            arbeit_mental_soll += duration_hour
        elif eve.event_type == 'SW':
            arbeit_shallow_soll += duration_hour
        elif eve.event_type == 'FZ':
            freizeit_soll += duration_hour
        elif eve.event_type == 'ORG':
            organisation_soll += duration_hour
    zeit_soll = [arbeit_mental_soll, arbeit_shallow_soll, freizeit_soll, organisation_soll]
    daten = {
        'labels': label,
        'zeit_ist': zeit_ist,
        'zeit_soll': zeit_soll
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
        if day.datum not in datum:
            datum.append(day.datum)
            mentale_arbeit.append(float(day.zeit_arbeit_mental))
            leichte_arbeit.append(float(day.zeit_arbeit_shallow))
        else:
            datums_index = datum.index(day.datum)
            mentale_arbeit[datums_index] += float(day.zeit_arbeit_mental)
            leichte_arbeit[datums_index] += float(day.zeit_arbeit_shallow)
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
    end_date = datetime.today()
    start_date = end_date - timedelta (days=60)
    Lerntage = Lerntag.objects.filter(datum__range=(start_date, end_date))
    mentale_arbeit_30 = []
    leichte_arbeit_30 = []
    mentale_arbeit_60 = []
    leichte_arbeit_60 = []
    datum = []
    count = 0
    for day in Lerntage:
        if count < 30:
            if day.datum not in datum:
                count += 1
                datum.append(day.datum)
                mentale_arbeit_30.append(float(day.zeit_arbeit_mental))
                leichte_arbeit_30.append(float(day.zeit_arbeit_shallow))
            else:
                count += 1
                datums_index = datum.index(day.datum)
                mentale_arbeit_30[datums_index] += float(day.zeit_arbeit_mental)
                leichte_arbeit_30[datums_index] += float(day.zeit_arbeit_shallow)
        elif count < 60:
            if day.datum not in datum:
                count += 1
                datum.append(day.datum)
                mentale_arbeit_60.append(float(day.zeit_arbeit_mental))
                leichte_arbeit_60.append(float(day.zeit_arbeit_shallow))
            else:
                count += 1
                datums_index = datum.index(day.datum)
                mentale_arbeit_60[datums_index] += float(day.zeit_arbeit_mental)
                leichte_arbeit_60[datums_index] += float(day.zeit_arbeit_shallow)
    daten = {
        'labels': datum,
        'mentaleArbeit30': mentale_arbeit_30,
        'leichteArbeit30': leichte_arbeit_30,
        'mentaleArbeit60': mentale_arbeit_60,
        'leichteArbeit60': leichte_arbeit_60,
    }
    return JsonResponse(daten)


# Zeiteinsatz über Monat als Kuchendiagramm
def zeiteinsatz_monat_view(request):
    end_date = datetime.today()
    start_date = end_date - timedelta (days=30)
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

# Produktivität, Wohlbefinden und Deepwork Zeit
def zeiteinsatz_monat_combined_productivity_view(request):
    end_date = datetime.today()
    start_date = end_date - timedelta (days=30)
    Lerntage = Lerntag.objects.filter(datum__range=(start_date, end_date))
    daten = {}
    count = 0
    for day in Lerntage:
        DW = day.zeit_arbeit_mental
        HAP = day.output_happiness
        PROD = day.output_productivity
        daten[count]={
            'x': DW,
            'y': HAP,
            'r': PROD
        }
        count += 1
    return JsonResponse(daten)

# Liniendiagramm alle Kategorien über Monat
def zeiteinsatz_monat_all_cat_view(request):
    end_date = datetime.today()
    start_date = end_date - timedelta (days=30)
    Lerntage = Lerntag.objects.filter(datum__range=(start_date, end_date))
    mentale_arbeit = []
    leichte_arbeit = []
    freizeit = []
    organisation = []
    datum = []
    for day in Lerntage:
        if day.datum not in datum:
            datum.append(day.datum)
            mentale_arbeit.append(float(day.zeit_arbeit_mental))
            leichte_arbeit.append(float(day.zeit_arbeit_shallow))
            freizeit.append(float(day.zeit_freizeit))
            organisation.append(float(day.zeit_organisation))
        else:
            datums_index = datum.index(day.datum)
            mentale_arbeit[datums_index] += float(day.zeit_arbeit_mental)
            leichte_arbeit[datums_index] += float(day.zeit_arbeit_shallow)
            freizeit[datums_index] += float(day.zeit_freizeit)
            organisation[datums_index] += float(day.zeit_organisation)
    daten = {
        'labels': datum,
        'DW': mentale_arbeit,
        'SW': leichte_arbeit,
        'FZ': freizeit,
        'ORG': organisation
    }
    return JsonResponse(daten)