from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.student_dashboard, name='index'),
    path('mock-tests/', views.mock_tests_view, name='mock_tests'),
]
