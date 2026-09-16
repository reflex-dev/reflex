from __future__ import annotations

import dataclasses
import inspect
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest
from reflex_sdk import types
from reflex_sdk._decode import json_name

from tests.units.reflex_sdk.schema_check import load_components, model_problems

# The schema components each model decodes, checked against the snapshot so a
# backend change that breaks decoding fails here when the snapshot is refreshed.
SCHEMA_MODELS: dict[type, tuple[str, ...]] = {
    types.AccessScope: ("AccessJson",),
    types.User: (
        "GetAppHistoryResponseDeploymentUser",
        "GetAppInfoLatestDeploymentResponseUser",
        "GetProjectInfoAppDeploymentUserResponse",
    ),
    types.AppDeployment: ("GetAppInfoLatestDeploymentResponse",),
    types.App: ("GetAppInfoResponse",),
    types.VmType: ("GetAppHistoryResponseVMType",),
    types.DeploymentRecord: ("GetAppHistoryResponse",),
    types.ProjectTier: ("GetProjectsTierResponse",),
    types.ProjectRef: ("CreateProjectResponse",),
    types.ProjectSummary: ("GetProjectsResponse",),
    types.ProjectAppDeployment: ("GetProjectInfoAppDeploymentResponse",),
    types.ProjectApp: ("GetProjectInfoAppResponse",),
    types.Project: ("GetProjectInfoResponse",),
    types.Role: ("ProjectRoleResponse",),
    types.ProjectMember: ("ProjectUserResult",),
}

# Models of responses the schema leaves untyped; their shapes come from the
# backend source.
UNTYPED_MODELS = {types.Me, types.Token, types.AppSummary, types.LogRecord}


def test_every_model_is_checked_or_listed_as_untyped():
    models = {
        value
        for value in vars(types).values()
        if inspect.isclass(value)
        and dataclasses.is_dataclass(value)
        and value.__module__ == types.__name__
    }
    assert models == set(SCHEMA_MODELS) | UNTYPED_MODELS


@pytest.mark.parametrize(
    ("model", "component"),
    [
        (model, component)
        for model, components in SCHEMA_MODELS.items()
        for component in components
    ],
    ids=lambda value: value.__name__ if isinstance(value, type) else value,
)
def test_model_matches_schema(model: type, component: str):
    assert model_problems(model, load_components()[component], SCHEMA_MODELS) == []


@dataclass(frozen=True, kw_only=True)
class _Nested:
    """A nested model for checker tests."""

    name: str


@dataclass(frozen=True, kw_only=True)
class _Model:
    """A model for checker tests."""

    id: uuid.UUID
    count: int
    nested: _Nested | None
    tags: list[str]
    extra: str = ""


_COMPONENT = {
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "count": {"type": "integer"},
        "nested": {
            "anyOf": [{"$ref": "#/components/schemas/Nested"}, {"type": "null"}]
        },
        "tags": {"type": "array", "items": {"type": "string"}},
        "extra": {"type": "string"},
    },
    "required": ["id", "count", "nested", "tags"],
}


def _problems(**overrides: Any) -> list[str]:
    component = {
        **_COMPONENT,
        "properties": {**_COMPONENT["properties"], **overrides},
    }
    return model_problems(_Model, component, {_Nested: ("Nested",)})


def test_checker_accepts_matching_model():
    assert _problems() == []


@pytest.mark.parametrize(
    ("overrides", "problem"),
    [
        ({"count": {"type": "string"}}, "_Model.count: <class 'int'> does not match"),
        (
            {"count": {"anyOf": [{"type": "integer"}, {"type": "null"}]}},
            "_Model.count: the schema allows null but the SDK type does not",
        ),
        (
            {"id": {"type": "string", "format": "date-time"}},
            "_Model.id: <class 'uuid.UUID'> does not match",
        ),
        (
            {"tags": {"type": "array", "items": {"type": "integer"}}},
            "_Model.tags[]: <class 'str'> does not match",
        ),
        (
            {"nested": {"$ref": "#/components/schemas/Other"}},
            "_Model.nested: no SDK type accepts schema member",
        ),
    ],
)
def test_checker_reports_mismatches(overrides: dict[str, Any], problem: str):
    problems = _problems(**overrides)
    assert len(problems) == 1
    assert problems[0].startswith(problem)


@dataclass(frozen=True, kw_only=True)
class _RenamedModel:
    """A model with a field stored under another key, for checker tests."""

    owner_id: uuid.UUID = field(metadata=json_name("project_owner"))


def test_checker_uses_response_keys():
    component = {
        "properties": {"project_owner": {"type": "string", "format": "uuid"}},
        "required": ["project_owner"],
    }
    assert model_problems(_RenamedModel, component, {}) == []
    assert model_problems(
        _RenamedModel, {"properties": {"owner_id": {"type": "string"}}}, {}
    ) == ["_RenamedModel.owner_id: not in the schema"]


def test_checker_reports_missing_and_optional_fields():
    component = {
        "properties": {
            key: value
            for key, value in _COMPONENT["properties"].items()
            if key != "tags"
        },
        "required": ["id", "nested"],
    }
    assert model_problems(_Model, component, {_Nested: ("Nested",)}) == [
        "_Model.count: optional in the schema but required by the SDK",
        "_Model.tags: not in the schema",
    ]
