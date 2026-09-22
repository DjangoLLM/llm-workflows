from __future__ import annotations

import dataclasses
import enum
from typing import Any, Literal, Mapping

import pytest
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationError,
    field_validator,
)

from agents.adapters.inference.codex.schema import (
    CodexResponseValidationError,
    CodexSchemaError,
    build_codex_output_schema,
    validate_codex_output,
)


class _Tone(str, enum.Enum):
    CALM = "calm"
    DIRECT = "direct"


class _Detail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    enabled: bool


class _SupportedResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(alias="displayName", description="Wire alias")
    count: int = 7
    ratio: float
    accepted: bool
    tone: _Tone
    tags: list[str]
    detail: _Detail
    note: str | None = None
    empty: None


class _LiteralResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marker: Literal["codex-live-ok"]


def _walk_schema(value: object):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_schema(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_schema(child)


def test_build_schema_supports_bounded_fixed_models() -> None:
    schema = build_codex_output_schema(_SupportedResult)

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == [
        "displayName",
        "count",
        "ratio",
        "accepted",
        "tone",
        "tags",
        "detail",
        "note",
        "empty",
    ]
    assert schema["properties"]["displayName"] == {"type": "string"}
    assert schema["properties"]["count"] == {"type": "integer"}
    assert schema["properties"]["tags"] == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert schema["properties"]["note"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}]
    }
    assert schema["properties"]["empty"] == {"type": "null"}

    detail_schema = schema["$defs"]["_Detail"]
    assert detail_schema["type"] == "object"
    assert detail_schema["additionalProperties"] is False
    assert detail_schema["required"] == ["label", "enabled"]
    assert schema["properties"]["detail"] == {"$ref": "#/$defs/_Detail"}

    tone_schema = schema["$defs"]["_Tone"]
    assert tone_schema == {"type": "string", "enum": ["calm", "direct"]}

    for item in _walk_schema(schema):
        if isinstance(item, dict):
            assert "title" not in item
            assert "description" not in item
            assert "default" not in item


def test_build_schema_normalizes_single_literal_to_enum() -> None:
    schema = build_codex_output_schema(_LiteralResult)

    assert schema["properties"]["marker"] == {
        "type": "string",
        "enum": ["codex-live-ok"],
    }


def test_validate_output_uses_aliases_defaults_and_original_model() -> None:
    result = validate_codex_output(
        _SupportedResult,
        """{
            "displayName": "release",
            "count": 9,
            "ratio": 1.5,
            "accepted": true,
            "tone": "direct",
            "tags": ["one", "two"],
            "detail": {"label": "nested", "enabled": false},
            "note": null,
            "empty": null
        }""",
    )

    assert isinstance(result, _SupportedResult)
    assert result.display_name == "release"
    assert result.count == 9
    assert result.tone is _Tone.DIRECT
    assert isinstance(result.detail, _Detail)


def test_validate_output_requires_fields_that_have_python_defaults() -> None:
    with pytest.raises(
        CodexResponseValidationError, match=r"\$\.count.*required on the wire"
    ):
        validate_codex_output(
            _SupportedResult,
            """{
                "displayName": "release",
                "ratio": 1.5,
                "accepted": true,
                "tone": "calm",
                "tags": [],
                "detail": {"label": "nested", "enabled": true},
                "note": null,
                "empty": null
            }""",
        )


class _ValidatedResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    even: int

    @field_validator("even")
    @classmethod
    def require_even(cls, value: int) -> int:
        if value % 2:
            raise ValueError("must be even")
        return value


@pytest.mark.parametrize(
    ("raw_json", "message"),
    [
        ('{"even":"2"}', "strict validation"),
        ('{"even":3}', "must be even"),
        ('{"even":2,"extra":true}', "extra"),
        ('{"missing":2}', "even"),
        ('not json', "valid JSON"),
    ],
)
def test_validate_output_rejects_invalid_content(raw_json: str, message: str) -> None:
    with pytest.raises(CodexResponseValidationError, match=message) as exc_info:
        validate_codex_output(_ValidatedResult, raw_json)

    assert isinstance(exc_info.value.__cause__, ValidationError)


def test_validate_output_rejects_non_utf8_bytes() -> None:
    with pytest.raises(CodexResponseValidationError, match="UTF-8"):
        validate_codex_output(_ValidatedResult, b"\xff")


@dataclasses.dataclass
class _DataclassResult:
    value: str


class _RootResult(RootModel[list[str]]):
    pass


@pytest.mark.parametrize(
    "result_type",
    [None, dict, dict[str, str], Mapping[str, str], Any, str, _DataclassResult, _RootResult],
)
def test_build_schema_rejects_unsupported_result_types(result_type: object) -> None:
    with pytest.raises(CodexSchemaError, match=r"\$\.result_type"):
        build_codex_output_schema(result_type)


class _AllowsExtra(BaseModel):
    value: str


class _NestedAllowsExtra(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nested: _AllowsExtra


class _MappingField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: dict[str, str]


class _AnyField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Any


class _UnionField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str | int


class _ConstrainedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int = Field(gt=0)


class _SetField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: set[str]


@pytest.mark.parametrize(
    ("result_type", "location"),
    [
        (_AllowsExtra, r"\$"),
        (_NestedAllowsExtra, r"\$\.\$defs\._AllowsExtra"),
        (_MappingField, r"\$\.properties\.metadata"),
        (_AnyField, r"\$\.properties\.value"),
        (_UnionField, r"\$\.properties\.value"),
        (_ConstrainedField, r"\$\.properties\.count"),
        (_SetField, r"\$\.properties\.values"),
    ],
)
def test_build_schema_rejects_unsupported_fields_with_location(
    result_type: type[BaseModel], location: str
) -> None:
    with pytest.raises(CodexSchemaError, match=location):
        build_codex_output_schema(result_type)


class _RecursiveResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    child: _RecursiveResult | None = None


def test_build_schema_rejects_recursive_references_with_location() -> None:
    with pytest.raises(CodexSchemaError, match=r"\$\.\$defs\._RecursiveResult"):
        build_codex_output_schema(_RecursiveResult)
