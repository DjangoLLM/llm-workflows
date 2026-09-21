"""Single JSON-safe coercion used before persisting agent/pipeline payloads."""
from typing import Any

from pydantic_core import to_jsonable_python


def json_safe(value: Any) -> Any:
    """Coerce a value into JSON-serializable primitives.

    Handles UUIDs, datetimes, enums, dataclasses, Pydantic models, sets and
    nested mappings/sequences. Unknown types degrade to their string form
    rather than raising, so an odd output never fails a run at save time.
    """
    return to_jsonable_python(value, serialize_unknown=True)
