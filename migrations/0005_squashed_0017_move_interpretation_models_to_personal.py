from django.db import migrations


class Migration(migrations.Migration):
    replaces = [
        ("agents", "0005_interpretationrun_interpretationsegment"),
        ("agents", "0006_interpretationrun_corrected_text"),
        ("agents", "0007_syncedmodule_syncedproject_syncedtask_and_more"),
        ("agents", "0008_remove_syncedtask_module_remove_syncedtask_project_and_more"),
        ("agents", "0009_proposedproject"),
        ("agents", "0010_proposedmodule"),
        ("agents", "0011_remove_proposedmodule_context_summary_and_more"),
        ("agents", "0012_rename_module_name_proposedmodule_name_and_more"),
        ("agents", "0013_delete_proposedmodule"),
        ("agents", "0014_delete_proposedproject"),
        ("agents", "0015_proposedproject"),
        ("agents", "0016_remove_proposed_project"),
        ("agents", "0017_move_interpretation_models_to_personal"),
    ]

    dependencies = [("agents", "0004_pipelinestep_parents")]

    operations = []
