from __future__ import annotations

import dataclasses
import inspect
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

import pytest
from reflex_build_sdk import types
from reflex_build_sdk._async.resources.projects import (
    _EffectivePermissions,
    _TeamGrantResult,
    _TeamRevokeResult,
)
from reflex_build_sdk._decode import json_name
from reflex_build_sdk._deploy import UploadReservation, UploadTarget

from tests.units.reflex_build_sdk.schema_check import load_components, model_problems

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
    types.RolePreviewMember: ("RolePreviewMember",),
    types.RolePreviewTeam: ("RolePreviewTeam",),
    types.RoleUpdatePreview: ("RoleUpdatePreviewResponse",),
    types.TeamGrant: ("ProjectTeamGrantResponse",),
    types.PendingTeamChange: ("PendingTeamGrantResponse",),
    types.TeamGrants: ("ProjectTeamGrantsResponse",),
    types.AuditLogEntry: ("GetProjectAuditLogResponse",),
    types.UsageBalance: ("UsageBalanceResult",),
    types.UsageEntry: ("UsageHistoryEntry",),
    _EffectivePermissions: ("EffectivePermissionsResponse",),
    _TeamGrantResult: ("TeamGrantResult",),
    _TeamRevokeResult: ("TeamRevokeResult",),
    types.DeploymentReport: ("DeploymentFailureResponse",),
    UploadReservation: ("ReserveUploadResponse",),
    UploadTarget: ("UploadTargetResponse",),
    types.SecurityViolation: ("SecurityViolation",),
    types.SecurityReviewResult: ("SecurityReviewResult",),
    types.SecurityReviewJob: ("SecurityReviewJobResult",),
}

# Models of responses the schema leaves untyped; their shapes come from the
# backend source.
UNTYPED_MODELS = {
    types.Me,
    types.TokenAccess,
    types.Token,
    types.AppSummary,
    types.RunningDeployment,
    types.AppMove,
    types.ServiceNameChange,
    types.DnsRecord,
    types.CustomDomain,
    types.EnvironmentDeployment,
    types.Environment,
    types.EnvironmentsEnabled,
    types.NewEnvironment,
    types.Promotion,
    types.CopiedSecrets,
    types.ManagedDatabase,
    types.SignInStatus,
    types.EndUser,
    types.EndUserPage,
    types.EndUserBlock,
    types.SignInInvite,
    types.Audience,
    types.AudienceChange,
    types.InviteRemoval,
    types.LogRecord,
    types.HostnameReservation,
    types.Region,
    types.MachineSize,
    types.GcpConnection,
    types.GcpStatus,
    types.ProviderAccount,
    types.CloudRunManifest,
    types.ProviderChange,
    types.FullDeployChange,
    types.InstanceBoundsChange,
    types.GcpBlockingApp,
    types.GcpCheck,
    types.GcpVerification,
    types.GcpKeyRotation,
    # Built by the client rather than decoded from a response.
    types.LoginRequest,
    types.EndUserExport,
}


def test_every_model_is_checked_or_listed_as_untyped():
    models = {
        value
        for value in vars(types).values()
        if inspect.isclass(value)
        and dataclasses.is_dataclass(value)
        and value.__module__ == types.__name__
    }
    assert (
        models
        == {model for model in SCHEMA_MODELS if model.__module__ == types.__name__}
        | UNTYPED_MODELS
    )


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
    level: Literal[1, 2] = 1
    extra: str = ""


_COMPONENT = {
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "count": {"type": "integer"},
        "nested": {
            "anyOf": [{"$ref": "#/components/schemas/Nested"}, {"type": "null"}]
        },
        "tags": {"type": "array", "items": {"type": "string"}},
        "level": {"enum": [1, 2]},
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
    assert _problems(level={"const": 2}) == []


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
        (
            {"level": {"enum": [True]}},
            "_Model.level: typing.Literal[1, 2] does not accept every value",
        ),
        (
            {"level": {"const": 3}},
            "_Model.level: typing.Literal[1, 2] does not accept every value",
        ),
        (
            {"level": {"type": "integer"}},
            "_Model.level: typing.Literal[1, 2] does not accept every value",
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
