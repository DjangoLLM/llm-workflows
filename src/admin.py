from django.contrib import admin

from .models import (
    AgentRun,
    PipelineRun,
    PipelineStep,
)


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("id", "agent_label", "status", "started_at", "ended_at")
    list_filter = ("status",)
    search_fields = ("agent_label", "id")
    date_hierarchy = "started_at"


@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = ("id", "pipeline_name", "status", "current_step", "created_at")
    list_filter = ("status", "pipeline_name")
    search_fields = ("pipeline_name", "id")
    date_hierarchy = "created_at"


@admin.register(PipelineStep)
class PipelineStepAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "step_name", "status", "order_index", "created_at")
    list_filter = ("status", "run__pipeline_name")
    search_fields = ("step_name", "run__id")
    date_hierarchy = "created_at"


