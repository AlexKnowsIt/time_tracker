from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.

def dashboard_data_view(request):
    return HttpResponse ('<h1>Hier kommt das Dashboard hin</h1>')