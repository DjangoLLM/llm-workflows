from __future__ import annotations

import asyncio

import pytest
from django.conf import settings
from temporalio.client import Client


@pytest.mark.live
def test_temporal_server_reachable() -> None:
    async def _connect() -> str:
        client = await Client.connect(settings.TEMPORAL_SERVER_URL)
        namespace = await client.service_client.workflow_service.describe_namespace(
            namespace="default"
        )
        return namespace.namespace_info.name

    namespace_name = asyncio.run(_connect())

    assert namespace_name == "default"
