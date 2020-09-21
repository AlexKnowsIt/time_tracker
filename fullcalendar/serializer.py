from rest_framework import serializers
from .models import Events
from datetime import timedelta, datetime
from django.contrib.auth.models import User

class EventsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Events
        fields = ['even_id', 'event_name', 'start_date', 'end_date', 'event_type']


class UserSerializer(serializers.ModelSerializer):
    evente = serializers.PrimaryKeyRelatedField(many=True, queryset=Events.objects.all())

    class Meta:
        model = User
        fields = ['id', 'username', 'evente']