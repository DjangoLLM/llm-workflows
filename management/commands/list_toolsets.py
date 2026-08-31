from __future__ import annotations

from django.core.management.base import BaseCommand

from agents.core.tools.registry import default_registry


class Command(BaseCommand):
    help = "List registered ToolSets, with optional module and expose-mcp filtering."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--module",
            action="append",
            default=None,
            help="Filter by AppConfig label. Repeatable.",
        )
        parser.add_argument(
            "--exposed-only",
            action="store_true",
            default=False,
            help="Only list toolsets registered with expose_mcp=True.",
        )

    def handle(self, *args, **options) -> None:
        modules = options.get("module")
        names = default_registry.toolset_names(
            modules=modules,
            exposed_only=options.get("exposed_only", False),
        )
        for name in names:
            module = default_registry.toolset_module(name)
            exposed = default_registry.toolset_exposed(name)
            tools = ",".join(t.name for t in default_registry.resolve_toolset(name))
            line = (
                f"{name}\t{module}\texposed={'true' if exposed else 'false'}"
                f"\ttools={tools}"
            )
            self.stdout.write(line)
