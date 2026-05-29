from django.shortcuts import render
from .models import Course

def home(request):
    courses = Course.objects.filter(is_active=True)

    context = {
        'courses': courses,
    }
    return render(request, 'website/home.html', context)
