from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run a FastMCP server exposing one registered ToolSet."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--toolset", required=True)
        parser.add_argument(
            "--transport",
            choices=["stdio", "http", "sse"],
            default="stdio",
        )
        parser.add_argument("--host", default="127.0.0.1")
        parser.add_argument("--port", type=int, default=None)
        parser.add_argument("--name", default=None)

    def handle(self, *args, **options) -> None:
        from agents.core.tools.mcp.runner import run

        run(
            options["toolset"],
            transport=options["transport"],
            host=options["host"],
            port=options["port"],
            name=options["name"],
        )
