"""Wait until the Temporal frontend port accepts TCP connections."""

from __future__ import annotations

import os
import socket
import time


def _host_port(url: str) -> tuple[str, int]:
    if "://" in url:
        url = url.split("://", 1)[1]
    host_port = url.split("/", 1)[0]
    if ":" not in host_port:
        return host_port, 7233
    host, port = host_port.rsplit(":", 1)
    return host, int(port)


def main() -> None:
    host, port = _host_port(os.environ.get("TEMPORAL_SERVER_URL", "localhost:7233"))
    deadline = time.monotonic() + int(os.environ.get("TEMPORAL_WAIT_SECONDS", "60"))

    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            try:
                sock.connect((host, port))
            except OSError:
                time.sleep(1)
                continue
            return

    raise SystemExit(f"Temporal was not reachable at {host}:{port}.")


if __name__ == "__main__":
    main()
