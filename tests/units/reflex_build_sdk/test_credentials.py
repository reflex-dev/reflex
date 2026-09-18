from __future__ import annotations

import json
from pathlib import Path

import pytest
import reflex_build_sdk.credentials

# Bound at import, before the autouse fixture points the module at a temporary file.
from reflex_build_sdk.credentials import (
    credentials_path,
    delete_token,
    load_token,
    save_token,
)


def test_credentials_path_is_the_reflex_login_file():
    path = credentials_path()
    assert path.name == "hosting_v1.json"
    assert path.parent.name == "reflex"


def test_load_token(tmp_path: Path):
    (tmp_path / "hosting_v1.json").write_text('{"access_token": "abc", "project": "p"}')
    assert load_token() == "abc"


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
def test_load_token_without_a_usable_token(tmp_path: Path, content: str | None):
    if content is not None:
        (tmp_path / "hosting_v1.json").write_text(content)
    assert load_token() is None


def test_load_token_unreadable(tmp_path: Path):
    (tmp_path / "hosting_v1.json").mkdir()
    assert load_token() is None


def test_save_token_keeps_other_settings(tmp_path: Path):
    path = tmp_path / "hosting_v1.json"
    path.write_text('{"access_token": "old", "project": "p"}')
    save_token("new")
    assert json.loads(path.read_text()) == {"access_token": "new", "project": "p"}
    assert load_token() == "new"
    assert [child.name for child in tmp_path.iterdir()] == ["hosting_v1.json"]


@pytest.mark.parametrize("content", [None, "not json", "[]"])
def test_save_token_starts_over_without_a_readable_file(
    tmp_path: Path, content: str | None
):
    path = tmp_path / "hosting_v1.json"
    if content is not None:
        path.write_text(content)
    save_token("new")
    assert json.loads(path.read_text()) == {"access_token": "new"}


def test_save_token_creates_the_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    path = tmp_path / "reflex" / "hosting_v1.json"
    monkeypatch.setattr(reflex_build_sdk.credentials, "credentials_path", lambda: path)
    save_token("new")
    assert json.loads(path.read_text()) == {"access_token": "new"}


def test_save_token_leaves_the_file_intact_when_writing_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    path = tmp_path / "hosting_v1.json"
    path.write_text('{"access_token": "old"}')

    def fail(*args: object, **kwargs: object) -> None:
        msg = "disk full"
        raise OSError(msg)

    monkeypatch.setattr(json, "dump", fail)
    with pytest.raises(OSError, match="disk full"):
        save_token("new")
    assert json.loads(path.read_text()) == {"access_token": "old"}
    assert [child.name for child in tmp_path.iterdir()] == ["hosting_v1.json"]


def test_delete_token_keeps_other_settings(tmp_path: Path):
    path = tmp_path / "hosting_v1.json"
    path.write_text('{"access_token": "old", "project": "p"}')
    delete_token()
    assert json.loads(path.read_text()) == {"project": "p"}
    assert load_token() is None


@pytest.mark.parametrize("content", [None, "not json", '{"project": "p"}'])
def test_delete_token_without_a_saved_token(tmp_path: Path, content: str | None):
    path = tmp_path / "hosting_v1.json"
    if content is not None:
        path.write_text(content)
    delete_token()
    assert (path.read_text() if content is not None else None) == content
