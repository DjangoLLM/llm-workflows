from __future__ import annotations

import enum
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel

from agents.core.json_safe import json_safe


class DemoEnum(enum.Enum):
    VALUE = "value"


@dataclass
class DemoData:
    value: int


class DemoOutput(BaseModel):
    task_id: uuid.UUID
    tags: dict[str, uuid.UUID]


def test_normalizes_nested_values() -> None:
    assert json_safe(
        {
            "id": uuid.UUID("12345678-1234-5678-1234-567812345678"),
            "at": datetime(2026, 5, 1, 12, 0, 0),
            "enum": DemoEnum.VALUE,
            "data": DemoData(value=3),
            "items": (DemoData(value=4),),
        }
    ) == {
        "id": "12345678-1234-5678-1234-567812345678",
        "at": "2026-05-01T12:00:00",
        "enum": "value",
        "data": {"value": 3},
        "items": [{"value": 4}],
    }


def test_uuids_nested_in_mappings_and_keys() -> None:
    key = uuid.UUID("12345678-1234-5678-1234-567812345678")
    value = uuid.UUID("87654321-4321-8765-4321-876543218765")

    result = json_safe({"outer": {key: {"inner": [value]}}})

    assert result == {"outer": {str(key): {"inner": [str(value)]}}}
    json.dumps(result)


def test_typed_output_with_uuids() -> None:
    task_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    tag_id = uuid.UUID("87654321-4321-8765-4321-876543218765")

    result = json_safe(DemoOutput(task_id=task_id, tags={"primary": tag_id}))

    assert result == {"task_id": str(task_id), "tags": {"primary": str(tag_id)}}
    json.dumps(result)


def test_unknown_type_degrades_instead_of_raising() -> None:
    class Opaque:
        def __repr__(self) -> str:
            return "<opaque>"

    json.dumps(json_safe({"thing": Opaque()}))
