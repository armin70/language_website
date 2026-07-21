from django.urls import path

from . import views


app_name = "toefl"


urlpatterns = [
    # ==================================================
    # Continuous TOEFL entry and final result
    # ==================================================
    path(
        "test/<slug:slug>/",
        views.take_mock_test_view,
        name="take_mock_test",
    ),
    path(
        "test/<slug:slug>/result/",
        views.full_test_result_view,
        name="full_test_result",
    ),

    path(
        "test/<slug:slug>/intro/<str:section>/<int:step>/",
        views.section_intro_view,
        name="section_intro",
    ),
    path(
        "test/<slug:slug>/<str:section>/module/<int:module_id>/intro/",
        views.module_intro_view,
        name="module_intro",
    ),

    # ==================================================
    # Reading — module based
    # ==================================================
    path(
        "test/<slug:slug>/reading/",
        views.take_reading_test_view,
        name="take_reading_test",
    ),
    path(
        "test/<slug:slug>/reading/module/<int:module_id>/",
        views.reading_module_view,
        name="reading_module",
    ),
    path(
        "reading/module-attempt/<int:module_attempt_id>/save/",
        views.save_reading_module_progress_view,
        name="save_reading_module_progress",
    ),
    path(
        "reading/module-attempt/<int:module_attempt_id>/submit/",
        views.submit_reading_module_view,
        name="submit_reading_module",
    ),
    path(
        "reading-attempt/<int:attempt_id>/result/",
        views.test_result_view,
        name="test_result",
    ),

    # ==================================================
    # Listening — existing block flow
    # ==================================================
    path(
        "test/<slug:slug>/listening/",
        views.take_listening_test_view,
        name="take_listening_test",
    ),
    path(
        "test/<slug:slug>/listening/block/<int:block_id>/",
        views.listening_block_view,
        name="listening_block",
    ),
    path(
        "listening-attempt/<int:attempt_id>/result/",
        views.listening_result_view,
        name="listening_result",
    ),

    # ==================================================
    # Writing — module based
    # ==================================================
    path(
        "test/<slug:slug>/writing/",
        views.take_writing_test_view,
        name="take_writing_test",
    ),
    path(
        "test/<slug:slug>/writing/module/<int:module_id>/",
        views.writing_module_view,
        name="writing_module",
    ),
    path(
        "writing/module-attempt/<int:module_attempt_id>/save/",
        views.save_writing_module_progress_view,
        name="save_writing_module_progress",
    ),
    path(
        "writing/module-attempt/<int:module_attempt_id>/submit/",
        views.submit_writing_module_view,
        name="submit_writing_module",
    ),
    path(
        "test/<slug:slug>/writing/block/<int:block_id>/",
        views.writing_block_view,
        name="writing_block",
    ),
    path(
        "writing-attempt/<int:attempt_id>/result/",
        views.writing_result_view,
        name="writing_result",
    ),

    # ==================================================
    # Speaking — all blocks loaded once
    # ==================================================
    path(
        "test/<slug:slug>/speaking/",
        views.take_speaking_test_view,
        name="take_speaking_test",
    ),
    path(
        "test/<slug:slug>/speaking/block/<int:block_id>/",
        views.speaking_block_view,
        name="speaking_block",
    ),
    path(
        "speaking-attempt/<int:attempt_id>/result/",
        views.speaking_result_view,
        name="speaking_result",
    ),
]
