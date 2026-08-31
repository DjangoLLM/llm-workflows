"""Routes for the feedback demo app."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "feedback"

urlpatterns = [
    path("", views.index, name="index"),
    path("start/", views.start, name="start"),
    path("runs/<uuid:run_id>/", views.index, name="run_detail"),
    path("runs/<uuid:run_id>/status/", views.run_status, name="run_status"),
    path("tools/", views.tool_playground, name="tool_playground"),
    path("tools/invoke/", views.tool_invoke, name="tool_invoke"),
]
