from django.shortcuts import render
from django.http import JsonResponse
from .models import Lerntag
from .forms import LerntagForm

# Create your views here.
def input_web_view(request):
    my_form = LerntagForm
    context = {
        'form': my_form
    }
    return render(request, 'input.html', context)