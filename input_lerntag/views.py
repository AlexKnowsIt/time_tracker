from django.shortcuts import render
from django.http import JsonResponse
from .models import Lerntag
from .forms import LerntagForm

# Create your views here.
def create_lerntag(request):
    my_form = LerntagForm
    context = {
        'form': my_form
    }
    return render(request, 'input.html', context)