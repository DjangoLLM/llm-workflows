from __future__ import annotations

from temporalio.activity import _Definition as ActivityDefinition

from agents.temporal.activities import (
    create_pipeline_run_activity,
    get_registered_step_activities,
    handle_meeting_notes_activity,
    handle_module_creation_activity,
    handle_random_brain_dump_activity,
    handle_status_update_activity,
    mark_pipeline_failed_activity,
    mark_pipeline_success_activity,
)
from agents.temporal.worker_plugins import TemporalActivityRegistration, TemporalWorkerPlugin


def get_temporal_worker_plugin() -> TemporalWorkerPlugin:
    static_activities = [
        TemporalActivityRegistration(
            activity_name="agents.create_pipeline_run_activity",
            activity_callable=create_pipeline_run_activity,
        ),
        TemporalActivityRegistration(
            activity_name="agents.mark_pipeline_success_activity",
            activity_callable=mark_pipeline_success_activity,
        ),
        TemporalActivityRegistration(
            activity_name="agents.mark_pipeline_failed_activity",
            activity_callable=mark_pipeline_failed_activity,
        ),
        TemporalActivityRegistration(
            activity_name="agents.handle_meeting_notes_activity",
            activity_callable=handle_meeting_notes_activity,
        ),
        TemporalActivityRegistration(
            activity_name="agents.handle_module_creation_activity",
            activity_callable=handle_module_creation_activity,
        ),
        TemporalActivityRegistration(
            activity_name="agents.handle_status_update_activity",
            activity_callable=handle_status_update_activity,
        ),
        TemporalActivityRegistration(
            activity_name="agents.handle_random_brain_dump_activity",
            activity_callable=handle_random_brain_dump_activity,
        ),
    ]

    generated_activities: list[TemporalActivityRegistration] = []
    for activity_callable in get_registered_step_activities():
        generated_activities.append(
            TemporalActivityRegistration(
                activity_name=ActivityDefinition.must_from_callable(activity_callable).name,
                activity_callable=activity_callable,
            )
        )

    return TemporalWorkerPlugin(
        plugin_slug="agents",
        workflows=[],
        activities=[*static_activities, *generated_activities],
    )
