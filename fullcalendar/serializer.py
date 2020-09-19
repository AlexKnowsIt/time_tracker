from rest_framework import serializers
from .models import Events
from datetime import timedelta, datetime

class EventsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Events
        fields = ['even_id', 'event_name', 'start_date', 'end_date', 'event_type']