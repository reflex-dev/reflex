"""Generated Python stubs and their hashes must not depend on the host encoding."""

import ast
import io
import json
import sys
from hashlib import md5
from pathlib import Path

import pytest
from reflex_base.utils import pyi_generator


@pytest.mark.parametrize("default_encoding", ["cp1252", "ascii", "utf-8"])
@pytest.mark.parametrize("text", ["Bullet: •", "Language: 中文"])
@pytest.mark.parametrize("prune_stale", [False, True])
def test_generated_stubs_use_utf8(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    default_encoding: str,
    text: str,
    prune_stale: bool,
) -> None:
    """Real stub generation and hashing work under non-UTF-8 filesystem defaults.

    Args:
        tmp_path: Temporary package root.
        monkeypatch: Fixture used to emulate a non-UTF-8 locale on every platform.
        default_encoding: Encoding used when a filesystem call omits it.
        text: Unicode documentation copied into the generated stub.
        prune_stale: Whether the registry is replaced or merged.
    """
    package_name = "unicode_stub_fixture"
    package = tmp_path / package_name
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    source = (
        "from reflex_base.components.component import Component\n"
        "from reflex_base.vars.base import Var\n\n"
        "class Widget(Component):\n"
        f"    # {text}\n"
        "    value: Var[str]\n"
    )
    (package / "widget.py").write_text(source, encoding="utf-8")
    registry = tmp_path / "pyi_hashes.json"
    previous_hashes = {"unrelated/stale.pyi": "previous-hash"}
    registry.write_text(json.dumps(previous_hashes), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pyi_generator, "PWD", tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    monkeypatch.delitem(sys.modules, package_name, raising=False)
    monkeypatch.delitem(sys.modules, f"{package_name}.widget", raising=False)

    def locale_encoding(encoding: str | None, stacklevel: int = 2) -> str:
        """Emulate a legacy locale while honoring explicit encodings.

        Args:
            encoding: The requested encoding, if any.
            stacklevel: The warning stack level supplied by pathlib.

        Returns:
            The explicit encoding or the emulated locale default.
        """
        if encoding is None or encoding == "locale":
            return default_encoding
        return encoding

    monkeypatch.setattr(io, "text_encoding", locale_encoding)
    try:
        pyi_generator.PyiGenerator().scan_all(
            [f"{package_name}/widget.py"], use_json=True, prune_stale=prune_stale
        )
    finally:
        sys.modules.pop(f"{package_name}.widget", None)
        sys.modules.pop(package_name, None)
    stub = package / "widget.pyi"
    content = stub.read_text(encoding="utf-8")
    assert text in content
    ast.parse(stub.read_bytes())
    hashes = json.loads(registry.read_text(encoding="utf-8"))
    expected_hashes = {} if prune_stale else dict(previous_hashes)
    expected_hashes[f"{package_name}/widget.pyi"] = md5(content.encode()).hexdigest()
    assert hashes == expected_hashes
