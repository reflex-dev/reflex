from __future__ import annotations

from pathlib import Path

import pytest

# Bound at import, before the autouse fixture points the module at a temporary file.
from reflex_sdk._credentials import credentials_path, load_stored_token


def test_credentials_path_is_the_reflex_login_file():
    path = credentials_path()
    assert path.name == "hosting_v1.json"
    assert path.parent.name == "reflex"


def test_load_stored_token(tmp_path: Path):
    (tmp_path / "hosting_v1.json").write_text('{"access_token": "abc", "project": "p"}')
    assert load_stored_token() == "abc"


@pytest.mark.parametrize(
    "content",
    [
        None,
        "not json",
        "[]",
        "{}",
        '{"access_token": ""}',
        '{"access_token": 5}',
    ],
)
def test_load_stored_token_without_a_usable_token(tmp_path: Path, content: str | None):
    if content is not None:
        (tmp_path / "hosting_v1.json").write_text(content)
    assert load_stored_token() is None


def test_load_stored_token_unreadable(tmp_path: Path):
    (tmp_path / "hosting_v1.json").mkdir()
    assert load_stored_token() is None
