from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("day/<int:day_id>/", views.day_view, name="day_view"),
]
