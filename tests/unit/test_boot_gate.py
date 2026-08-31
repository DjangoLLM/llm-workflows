"""Assert that non-MCP Django commands never import `agents.core.tools.mcp.runner`.

The runner is the only module that starts a FastMCP transport; if it isn't
imported, no port is opened. We verify by spawning a subprocess running the
target command, dumping `sys.modules` at exit, and asserting the runner is
absent. This is the boot-gate AC from the work-item HLD §2 and parent HLD §8.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import pytest


_RUNNER = "agents.core.tools.mcp.runner"


def _run_with_module_capture(invocation: str) -> set[str]:
    """Run `invocation` in a subprocess and return the resulting sys.modules names."""
    fd, dump_path = tempfile.mkstemp(prefix="boot_gate_modules_", suffix=".json")
    os.close(fd)

    script = (
        "import atexit, json, sys\n"
        f"_DUMP = {dump_path!r}\n"
        "def _flush():\n"
        "    with open(_DUMP, 'w') as fh:\n"
        "        json.dump(list(sys.modules), fh)\n"
        "atexit.register(_flush)\n"
        "try:\n"
        + "".join("    " + ln + "\n" for ln in invocation.splitlines())
        + "except SystemExit:\n"
        "    pass\n"
        "except Exception:\n"
        "    pass\n"
    )

    try:
        env = os.environ.copy()
        env.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
        env.setdefault(
            "DATABASE_URL",
            "postgres://postgres:postgrespassword@127.0.0.1:5433/agents_unit_test",
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            cwd="/tmp",
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"subprocess failed: stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        with open(dump_path) as fh:
            return set(json.load(fh))
    finally:
        os.unlink(dump_path)


@pytest.mark.parametrize(
    "invocation",
    [
        # `manage.py check` equivalent — full Django setup + system check.
        "import django\ndjango.setup()\n"
        "from django.core.management import call_command\n"
        "call_command('check')",
        # `manage.py shell -c 'pass'` equivalent.
        "import django\ndjango.setup()",
        # `manage.py migrate --check`. Likely fails because the test DB
        # may not have agents tables migrated — but the gate is about
        # *imports*: even partial execution must not pull in the runner.
        "import django\ndjango.setup()\n"
        "from django.core.management import call_command\n"
        "call_command('migrate', '--check')",
        # `manage.py run_temporal_worker --help` — exits via SystemExit.
        "import django\ndjango.setup()\n"
        "from django.core.management import call_command\n"
        "call_command('run_temporal_worker', '--help')",
    ],
    ids=["check", "shell", "migrate", "run_temporal_worker_help"],
)
def test_runner_not_imported_by_command(invocation):
    modules = _run_with_module_capture(invocation)
    assert _RUNNER not in modules, (
        f"{_RUNNER} was imported by:\n  {invocation!r}\n"
        f"mcp-related modules: {sorted(m for m in modules if 'mcp' in m)}"
    )


def test_list_toolsets_does_not_import_runner():
    invocation = (
        "import django\ndjango.setup()\n"
        "from django.core.management import call_command\n"
        "call_command('list_toolsets')"
    )
    modules = _run_with_module_capture(invocation)
    assert _RUNNER not in modules, (
        f"list_toolsets must not pull in {_RUNNER}; "
        f"mcp-related modules: {sorted(m for m in modules if 'mcp' in m)}"
    )
