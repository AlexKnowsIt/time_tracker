from django.shortcuts import render
from .models import Events
from .forms import KalenderForm
from datetime import datetime, timedelta, date
from django.http import JsonResponse, HttpResponseRedirect

def create_planung(request):
    my_form = KalenderForm(request.POST or None)
    if my_form.is_valid():
        my_form.save()
        return HttpResponseRedirect('')
    context = {
        'form': my_form
    }
    return render(request, 'input_planner.html', context)

def event_view(request):
    context = {
    }
    return render(request,'calendar.html',context)

def calendar_view(request):
    end_date = datetime.today() + timedelta (days=2)
    start_date = end_date - timedelta (days=7)
    Evente = Events.objects.filter(start_date__range=(start_date, end_date))
    data_DW = {}
    data_SW = {}
    data_FZ = {}
    data_ORG = {}
    data_other = {}
    count_DW = 0
    count_SW = 0
    count_FZ = 0
    count_ORG = 0
    count_other = 0
    for Event in Evente:
        start = Event.start_date
        ende = Event.end_date
        titel = Event.event_name
        kategorie = Event.event_type
        single_data = {'title': titel,
                'start': start,
                'end': ende,
                'category': kategorie}
        if kategorie == 'DW':
            data_DW[count_DW]=single_data
            count_DW += 1
        elif kategorie == 'SW':
            data_SW[count_SW]=single_data
            count_SW += 1
        elif kategorie == 'FZ':
            data_FZ[count_FZ]=single_data
            count_FZ += 1
        elif kategorie == 'ORG':
            data_ORG[count_ORG]=single_data
            count_ORG += 1
        else:
            data_other[count_other]=single_data
    daten = {
        'DW': data_DW,
        'SW': data_SW,
        'FZ': data_FZ,
        'ORG': data_ORG
    }
    return JsonResponse(daten)