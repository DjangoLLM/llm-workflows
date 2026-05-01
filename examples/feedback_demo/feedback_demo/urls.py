"""URL routes for the feedback demo project."""

from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("", include("feedback.urls")),
]
