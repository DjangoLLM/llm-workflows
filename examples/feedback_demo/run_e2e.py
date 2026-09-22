"""Full end-to-end run of the feedback demo on the host, no Docker.

Boots a Temporal dev server, the Temporal worker and the Django server as
subprocesses, submits feedback over HTTP exactly like the browser form does,
polls the PipelineRun ledger until the workflow is terminal, then tears
everything down. Exits 0 when the run SUCCEEDED, 1 otherwise.

Run from this directory:

    ../../.venv/bin/python run_e2e.py

Needs the `temporal` and authenticated `codex` CLIs on PATH.
Set CODEX_MODEL to override the model configured in Codex.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import socket
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent
WEB = "http://127.0.0.1:8000"
FEEDBACK = "Loved the onboarding flow, but the invoice page kept timing out."


def wait_port(port: int, seconds: int = 60) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.5)
    raise SystemExit(f"port {port} never opened")


def main() -> int:
    env = os.environ.copy()
    for binary in ("temporal", "codex"):
        if shutil.which(binary) is None:
            raise SystemExit(f"{binary} is required on PATH")
    tmp = tempfile.mkdtemp(prefix="feedback_e2e_")
    env.update(
        DJANGO_SETTINGS_MODULE="feedback_demo.settings",
        SQLITE_PATH=f"{tmp}/db.sqlite3",
        TEMPORAL_SERVER_URL="localhost:7233",
    )
    print(f"model={env.get('CODEX_MODEL', 'Codex default')}  tmp={tmp}")

    procs: list[subprocess.Popen] = []
    log = open(f"{tmp}/services.log", "w")

    def spawn(*cmd: str) -> None:
        procs.append(subprocess.Popen(cmd, cwd=DEMO_DIR, env=env, stdout=log, stderr=log))

    try:
        spawn("temporal", "server", "start-dev", "--headless", "--db-filename", f"{tmp}/temporal.db")
        wait_port(7233)
        subprocess.run(
            [sys.executable, "manage.py", "migrate", "--run-syncdb", "--noinput"],
            cwd=DEMO_DIR, env=env, check=True, stdout=log, stderr=log,
        )
        spawn(sys.executable, "manage.py", "run_temporal_worker")
        spawn(sys.executable, "manage.py", "runserver", "8000", "--noreload")
        wait_port(8000)

        # Browser-equivalent submit: fetch form for the CSRF cookie, then POST.
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        opener.open(f"{WEB}/").read()
        token = next(c.value for c in jar if c.name == "csrftoken")
        body = urllib.parse.urlencode({"csrfmiddlewaretoken": token, "feedback_text": FEEDBACK}).encode()
        req = urllib.request.Request(f"{WEB}/start/", data=body, headers={"Referer": f"{WEB}/"})
        resp = opener.open(req)  # follows the 302 to /runs/<id>/
        status_url = resp.geturl() + "status/"
        print("run:", resp.geturl())

        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            data = json.loads(opener.open(status_url).read())
            steps = [(s["step_name"], s["status"]) for s in data["steps"]]
            print(data["run"]["status"], steps)
            if data["is_terminal"]:
                break
            time.sleep(2)
        else:
            raise SystemExit("timed out waiting for the run to finish")

        print("final_output:", json.dumps(data["final_output"], indent=2))
        if data["error"]:
            print("error:", data["error"])
        ok = data["run"]["status"] == "SUCCEEDED" and data["final_output"] is not None
        print("PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        for p in reversed(procs):
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        log.close()
        print(f"logs: {tmp}/services.log")


if __name__ == "__main__":
    sys.exit(main())
