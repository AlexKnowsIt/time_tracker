from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def input_web_view(request):
    return HttpResponse ('<h1>Hier kommt der Input hin</h1>')