from django.apps import AppConfig


class AgentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agents'

    def ready(self):
        from agents import handlers  # noqa: F401
        from agents.core.agent_config_catalog import AgentConfigCatalog
        from agents.core.agent_config_registrations import register_all_agent_configs
        from agents.core.step_catalog import StepCatalog
        from agents.core.step_registrations import register_all_steps

        # Register configuration catalogs before runtime usage.

        register_all_agent_configs()
        register_all_steps()

        # Fail fast on invalid registration state.

        AgentConfigCatalog.validate_registry()
        StepCatalog.validate_registry()
