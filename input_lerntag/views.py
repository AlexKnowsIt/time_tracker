from django.shortcuts import render
from django.http import HttpResponseRedirect
from .models import Lerntag
from fullcalendar.models import Events
from .forms import LerntagForm
from datetime import datetime, timedelta
from datetime import date as Datum
from rest_framework.views import APIView, Response, status
from rest_framework import viewsets
from .serializer import LerntagSerializer

class TrendView(APIView):
    end_date = datetime.today()
    label = ['Deepwork', 'Shallow Work', 'Freizeit', 'Organisation']

    def get_time_frame(self, days):
        start_date = self.end_date - timedelta (days=days)
        Lerntage = Lerntag.objects.filter(datum__range=(start_date, self.end_date))

        return Lerntage

    def get(self, request, dashboard):

        if dashboard == 'month-work':
            # letzte 30 Tage Arbeit vs 30 Tage davor
            Lerntage = self.get_time_frame(60)
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
            return Response(daten)

        elif dashboard == 'month':
            # Zeiteinsatz über Monat als Kuchendiagramm
            Lerntage = self.get_time_frame(30)
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
                'labels': self.label,
                'daten': [mentale_arbeit, leichte_arbeit, freizeit, organisation]
            }
            return Response(daten)

        elif dashboard == 'month-summary':
            # Produktivität, Wohlbefinden und Deepwork Zeit
            Lerntage = self.get_time_frame(30)
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
            return Response(daten)

        elif dashboard == 'month-progress':
            # Liniendiagramm alle Kategorien über Monat
            Lerntage = self.get_time_frame(30)
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
            return Response(daten)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)

class DashboardView(APIView):
    
    end_date = datetime.today()
    label = ['Deepwork', 'Shallow Work', 'Freizeit', 'Organisation']

    def get_time_frame(self, days):
        start_date = self.end_date - timedelta (days=days)
        Lerntage = Lerntag.objects.filter(datum__range=(start_date, self.end_date))
        return Lerntage

    def get(self, request, dashboard):

        if dashboard == 'day':
            # Kuchendiagramm mit rel. und absoluten Werten für alle Kategorien
            Lerntage = self.get_time_frame(1)
            arbeit_mental = 0
            arbeit_shallow = 0
            freizeit = 0
            organisation = 0
            for day in Lerntage:
                arbeit_mental += day.zeit_arbeit_mental
                arbeit_shallow += day.zeit_arbeit_shallow
                freizeit += day.zeit_freizeit
                organisation += day.zeit_organisation
            daten_reihe = [arbeit_mental, arbeit_shallow, freizeit, organisation]
            daten = {
                'labels': self.label,
                'daten': daten_reihe
            }
            return Response(daten)

        elif dashboard == 'day-comp':
            # Barchart Ist Soll
            Lerntage = self.get_time_frame(1)
            Event = Events.objects.filter(start_date__date=datetime.today()) # To-Do: Hier gibt es eine Diskrepanz in der Zeitmessung der beiden Varianten
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
                'labels': self.label,
                'zeit_ist': zeit_ist,
                'zeit_soll': zeit_soll
            }
            return Response(daten)

        elif dashboard == 'week-work':
            # Liniendiagramm Arbeit (DW SW) im Zeitverlauf
            Lerntage = self.get_time_frame(7)
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
            return Response(daten)

        elif dashboard == 'week':
            # Kuchendiagramm mit rel. und absoluten Werten für alle Kategorien
            Lerntage = self.get_time_frame(7)
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
                'labels': self.label,
                'daten': [mentale_arbeit, leichte_arbeit, freizeit, organisation]
            }
            return Response(daten)
            
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
# Erstellt Lerntag Objekt aus Formular
def create_lerntag(request):
    my_form = LerntagForm(request.POST or None)
    if my_form.is_valid():
        my_form.save()
        return HttpResponseRedirect('')
    context = {
        'form': my_form
    }
    return render(request, 'input_tracker.html', context)