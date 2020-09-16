from rest_framework import serializers
from .models import Events
from datetime.datetime import now
from datetime import timedelta

class EventsSerializer(serializers.Serializer):
    even_id = serializers.AutoField(primary_key=True)
    event_name = serializers.CharField(max_length=255)
    jetzt = now()
    start_date = serializers.DateTimeField(default=jetzt)
    end_date = serializers.DateTimeField(null=True,blank=True, default=jetzt + datetime.timedelta(hours=2))
        event_type = serializers.CharField(
        max_length=3,
    )

    def create (self, validated_data):
        return Events.objects.create(validated_data)

    def update (self, instance, validated_data):
        instance.even_id = validated_data.get('even_id', instance.title)
        instance.event_name = validated_data.get('event_name', instance.event_name)
        instance.start_date = validated_data.get('start_date', instance.start_date)
        instance.end_date = validated_data.get('end_date', instance.end_date)
        instance.save()
        return instance