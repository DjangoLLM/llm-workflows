from __future__ import annotations

from unittest.mock import patch

import django
from django.apps import apps
from django.conf import settings
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.test import override_settings


LEGACY_MIGRATIONS = [
    "0001_initial",
    "0002_pipelinerun_pipelinestep",
    "0003_pipelinestep_agent_run",
    "0004_pipelinestep_parents",
    "0005_interpretationrun_interpretationsegment",
    "0006_interpretationrun_corrected_text",
    "0007_syncedmodule_syncedproject_syncedtask_and_more",
    "0008_remove_syncedtask_module_remove_syncedtask_project_and_more",
    "0009_proposedproject",
    "0010_proposedmodule",
    "0011_remove_proposedmodule_context_summary_and_more",
    "0012_rename_module_name_proposedmodule_name_and_more",
    "0013_delete_proposedmodule",
    "0014_delete_proposedproject",
    "0015_proposedproject",
    "0016_remove_proposed_project",
    "0017_move_interpretation_models_to_personal",
]
SQUASHED_TAIL = ("agents", "0005_squashed_0017_move_interpretation_models_to_personal")


def _configure_documented_dependency_settings() -> None:
    if settings.configured:
        return

    settings.configure(
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes", "agents"],
        SECRET_KEY="migration-loader-test",
    )
    django.setup()


def test_packaged_migration_graph_loads_without_host_project_apps() -> None:
    _configure_documented_dependency_settings()
    installed_app_labels = {config.label for config in apps.get_app_configs()}
    assert {"transcripts", "plane_agent", "personal"}.isdisjoint(installed_app_labels)

    with override_settings(MIGRATION_MODULES={"agents": "agents.migrations"}):
        loader = MigrationLoader(connection=None)

    assert loader.graph.leaf_nodes("agents") == [
        SQUASHED_TAIL
    ]


def test_standalone_migration_replaces_the_complete_legacy_chain() -> None:
    _configure_documented_dependency_settings()
    with override_settings(MIGRATION_MODULES={"agents": "agents.migrations"}):
        loader = MigrationLoader(connection=None)
    migration = loader.disk_migrations[SQUASHED_TAIL]

    assert migration.replaces == [
        ("agents", migration_name) for migration_name in LEGACY_MIGRATIONS[4:]
    ]


def test_installation_at_last_standalone_migration_uses_squashed_tail() -> None:
    _configure_documented_dependency_settings()
    applied = {
        ("agents", migration_name): object() for migration_name in LEGACY_MIGRATIONS[:4]
    }

    with (
        override_settings(MIGRATION_MODULES={"agents": "agents.migrations"}),
        patch.object(MigrationRecorder, "applied_migrations", return_value=applied),
    ):
        loader = MigrationLoader(connection=object())

    assert SQUASHED_TAIL in loader.graph.nodes
    assert ("agents", LEGACY_MIGRATIONS[4]) not in loader.graph.nodes
    assert SQUASHED_TAIL not in loader.applied_migrations


def test_fully_upgraded_legacy_installation_recognizes_squashed_tail() -> None:
    _configure_documented_dependency_settings()
    applied = {("agents", migration_name): object() for migration_name in LEGACY_MIGRATIONS}

    with (
        override_settings(MIGRATION_MODULES={"agents": "agents.migrations"}),
        patch.object(MigrationRecorder, "applied_migrations", return_value=applied),
    ):
        loader = MigrationLoader(connection=object())

    assert SQUASHED_TAIL in loader.graph.nodes
    assert SQUASHED_TAIL in loader.applied_migrations
