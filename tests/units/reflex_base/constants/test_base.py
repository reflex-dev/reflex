"""Tests for reflex_base.constants.base."""

from __future__ import annotations

from pathlib import Path
from typing import get_args

from reflex_base.constants.base import LITERAL_ENV, Env, Templates, _web_template_dir


def test_literal_env_matches_env_enum():
    """LITERAL_ENV must stay in sync with the Env enum values."""
    assert set(get_args(LITERAL_ENV)) == {env.value for env in Env}


def test_web_template_dir_prefers_the_embedded_copy(tmp_path: Path):
    """A built distribution carries the frontend inside the package."""
    root_dir = tmp_path / "site-packages" / "reflex_base"
    embedded = root_dir / ".templates" / "web"
    embedded.mkdir(parents=True)
    assert _web_template_dir(root_dir) == embedded


def test_web_template_dir_falls_back_to_the_checkout(tmp_path: Path):
    """A source checkout reads the frontend package beside reflex-base."""
    root_dir = tmp_path / "packages" / "reflex-base" / "src" / "reflex_base"
    root_dir.mkdir(parents=True)
    assert (
        _web_template_dir(root_dir) == tmp_path / "packages" / "reflex-frontend" / "src"
    )


def test_web_template_holds_the_frontend():
    """Whichever layout is installed, the template resolves to real files."""
    assert (Templates.Dirs.WEB_TEMPLATE / "utils" / "state.js").is_file()
