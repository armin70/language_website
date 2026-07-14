from django.urls import path
from . import views

app_name = 'toefl'

urlpatterns = [
    path('test/<slug:slug>/', views.take_mock_test_view, name='take_mock_test'),
    path('test/<slug:slug>/submit/<int:attempt_id>/', views.submit_mock_test_view, name='submit_mock_test'),
    path(
    "test/<slug:slug>/block/<int:block_id>/",
    views.reading_block_view,
    name="reading_block"
),
     path("attempt/<int:attempt_id>/result/", views.test_result_view, name="test_result"),
]
