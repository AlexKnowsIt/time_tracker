from django.shortcuts import render
from .models import Events
from .forms import KalenderForm
from datetime import datetime, timedelta, date
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
from rest_framework.views import APIView, Response, status
from rest_framework.parsers import JSONParser
from .serializer import EventsSerializer
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json

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


class CalendarLookView(APIView):
    def get(self, request):
        end_date = datetime.today() + timedelta (days=2)
        start_date = end_date - timedelta (days=7)
        evente = Events.objects.filter(start_date__range=(start_date, end_date)).filter()
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
        for Event in evente:
            identifier = Event.even_id
            start = Event.start_date
            ende = Event.end_date
            titel = Event.event_name
            kategorie = Event.event_type
            single_data = {'title': titel,
                            'start': start,
                            'end': ende,
                            'id': identifier
                            }
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

        return Response(daten)

def event_detail_view(request, id):
    """
    Retrieve, update or delete a code Events.
    """
    try:
        Event = Events.objects.get(even_id=id)
    except Events.DoesNotExist:
        return HttpResponse(status=404)

    if request.method == 'PUT':
        data = JSONParser().parse(request)
        serializer = EventsSerializer(Event, data=data)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data)
        return JsonResponse(serializer.errors, status=400)

class CalendarView(APIView): # Funktioniert nicht, gibt success Meldung aber es kommt nichts an
    def get_object(self, id):
        try:
            return Events.objects.get(even_id=id)

        except Events.DoesNotExist:
            return HttpResponse(status=status.HTTP_404_NOT_FOUND)

    def put(self, request, id, format=None):
        event = self.get_object(id)
        # data = JSONParser().parse(request)
        serializer = EventsSerializer(event, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)