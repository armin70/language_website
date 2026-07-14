from django.urls import path
from . import views

app_name = "website"

urlpatterns = [
    path('', views.home, name='home'),
    path('about', views.about, name='about'),
    path('contact', views.contact, name='contact'),
    path('free_discussion', views.free_discussion, name='free_discussion'),
    path('private_course', views.private_course, name='private_course'),
    path('toefl', views.toefl, name='toefl'),
    path(
        "consultation/request/",
        views.consultation_request_view,
        name="consultation_request",
    ),
    path(
        "contact/",
        views.contact_view,
        name="contact",
    ),
]
