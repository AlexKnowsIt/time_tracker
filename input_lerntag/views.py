from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def input_web_view(request):
    return render(request, 'input.html')