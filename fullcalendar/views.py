from django.shortcuts import render
from .models import Events
from datetime import datetime, timedelta, date
from django.http import JsonResponse

def event_view(request):
    context = {
    }
    return render(request,'calendar.html',context)

def calendar_view(request):
    end_date = datetime.today() + timedelta (days=2)
    start_date = end_date - timedelta (days=7)
    Evente = Events.objects.filter(start_date__range=(start_date, end_date))
    data = {}
    count = 0
    for Event in Evente:
        start = Event.start_date
        ende = Event.end_date
        titel = Event.event_name
        kategorie = Event.event_type
        single_data = {'title': titel,
                'start': start,
                'end': ende,
                'category': kategorie}
        data[count]=single_data
        count += 1
    daten = data
    return JsonResponse(daten)