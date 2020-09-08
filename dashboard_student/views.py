from django.shortcuts import render
from django.http import JsonResponse

# Create your views here.

# st = short-term
def dashboard_data_view_st(request):
    return render (request, 'dashboard_st.html')

# lt = long-term
def dashboard_data_view_lt(request):
    return render (request, 'dashboard_lt.html')