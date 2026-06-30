from django.urls import path
from .views import take_test

urlpatterns = [
    path("test/", take_test, name="placement_test"),
]
