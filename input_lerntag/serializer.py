from rest_framework import serializers
from .models import Lerntag

class LerntagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lerntag
        fields = '__all__'
