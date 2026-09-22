from django.apps import AppConfig


class AgentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agents'

    def ready(self):
        from agents import handlers  # noqa: F401
        from agents.catalog.agent_definition_catalog import AgentDefinitionCatalog
        from agents.catalog.choice_definition_catalog import ChoiceDefinitionCatalog
        from agents.runner.agent_definition_registrations import register_all_agent_definitions
        from agents.catalog.step_catalog import StepCatalog
        from agents.runner.step_registrations import register_all_steps
        from agents.runner.step_dispatch import StepDispatcher

        # Register configuration catalogs before runtime usage.

        register_all_agent_definitions()
        register_all_steps()

        # Fail fast on invalid registration state.

        AgentDefinitionCatalog.validate_registry()
        ChoiceDefinitionCatalog.validate_registry()
        StepCatalog.validate_registry()
        for key in StepCatalog.list_step_keys():
            StepDispatcher.resolve_agent_definition(StepCatalog.get_step(key))
