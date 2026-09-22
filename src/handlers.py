import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.dispatch import Signal
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)

agent_run_completed = Signal()


__all__ = ["agent_run_completed"]
