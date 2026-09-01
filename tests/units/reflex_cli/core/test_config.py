from __future__ import annotations

from typing import Any

import pytest
from reflex_cli.core.config import Config
from reflex_cli.utils.exceptions import ConfigInvalidFieldValueError


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("gcp_connection", 123),
        ("full_deploy", "false"),
        ("name", 1),
        ("strategy", []),
    ],
)
def test_optional_fields_are_validated(field: str, value: Any):
    """`X | None` fields validate on every supported Python, not just 3.14.

    They read as ``types.UnionType`` below 3.14, which the dispatcher used to
    miss: a quoted `full_deploy: "false"` was then sent to the server as a
    truthy string, and a numeric `gcp_connection` reached the resolver and
    crashed on `.strip()`.
    """
    with pytest.raises(ConfigInvalidFieldValueError):
        Config(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("gcp_connection", "eu-prod"),
        ("gcp_connection", None),
        ("full_deploy", True),
        ("full_deploy", False),
        ("full_deploy", None),
    ],
)
def test_new_gcp_fields_accept_their_types(field: str, value: Any):
    """The GCP settings take their own types, and None for "unset"."""
    assert getattr(Config(**{field: value}), field) == value


def test_full_deploy_defaults_to_unset():
    """Not False: a config file that never mentions it changes no app's mode."""
    assert Config().full_deploy is None
