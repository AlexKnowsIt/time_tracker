from .models import Events
from datetime import datetime, timedelta, date

end_date = datetime.today() + timedelta (days=2)
start_date = end_date - timedelta (days=7)
Evente = Events.objects.filter(start_date__range=(start_date, end_date))
data = {}
count_DW = 0
count_SW = 0
count_FZ = 0
count_ORG = 0
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
        data['DW'][count_DW]=single_data
        count_DW += 1
    elif kategorie == 'SW':
        data['SW'][count_SW]=single_data
        count_SW += 1
    elif kategorie == 'FZ':
        data['FZ'][count_FZ]=single_data
        count_FZ += 1
    elif kategorie == 'ORG':
        data['ORG'][count_ORG]=single_data
        count_ORG += 1
daten = data
print(daten)