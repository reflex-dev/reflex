"""Tests for the shared JSON parsing helper shipped in the web template."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import reflex_base

WEB_TEMPLATE = Path(reflex_base.__file__).parent / ".templates" / "web"
JSON_HELPER_PATH = WEB_TEMPLATE / "utils" / "helpers" / "json.js"

# Parses each payload with the helper and reports the result, using a JSON-safe
# encoding since NaN/Infinity cannot round-trip through JSON.stringify.
DRIVER = """
import { pathToFileURL } from "node:url";
const { parseJson } = await import(pathToFileURL(process.argv[2]).href);
const encode = (value) =>
  typeof value === "number" && !Number.isFinite(value)
    ? { nonFinite: String(value) }
    : value;
const results = JSON.parse(process.argv[3]).map((payload) => {
  try {
    return { ok: JSON.parse(JSON.stringify(parseJson(payload), (_k, v) => encode(v))) };
  } catch (e) {
    return { error: String(e) };
  }
});
process.stdout.write(JSON.stringify(results));
"""

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node missing")


def _parse_json(payloads: list[str], tmp_path: Path) -> list[dict]:
    """Parse each payload with the template helper in node.

    Args:
        payloads: The raw payloads to hand to the helper.
        tmp_path: Directory used to write the driver script.

    Returns:
        One ``{"ok": value}`` or ``{"error": message}`` entry per payload.
    """
    driver = tmp_path / "driver.mjs"
    driver.write_text(DRIVER)
    return json.loads(
        subprocess.run(
            ["node", str(driver), str(JSON_HELPER_PATH), json.dumps(payloads)],
            check=True,
            capture_output=True,
            encoding="utf-8",
        ).stdout
    )


def test_templates_do_not_import_json5() -> None:
    """No template may import json5.

    Regression for https://github.com/reflex-dev/reflex/issues/7163: json5's
    browser distribution embeds core-js 2.6.5, which then shows up in exported
    production bundles. The dependency was dropped in #6339 but the upload
    helper kept importing it, so it kept resolving transitively.
    """
    offenders = [
        path.relative_to(WEB_TEMPLATE).as_posix()
        for path in WEB_TEMPLATE.rglob("*.js")
        if "json5" in path.read_text(encoding="utf-8")
    ]

    assert not offenders, f"templates still reference json5: {offenders}"


def test_parses_python_non_finite_floats(tmp_path: Path) -> None:
    """Bare NaN/Infinity tokens from python's json.dumps are parsed.

    Args:
        tmp_path: Pytest temporary directory.
    """
    payload = json.dumps({
        "nan": float("nan"),
        "inf": float("inf"),
        "ninf": float("-inf"),
    })
    assert payload == '{"nan": NaN, "inf": Infinity, "ninf": -Infinity}'

    (result,) = _parse_json([payload], tmp_path)

    assert result == {
        "ok": {
            "nan": {"nonFinite": "NaN"},
            "inf": {"nonFinite": "Infinity"},
            "ninf": {"nonFinite": "-Infinity"},
        }
    }


def test_parses_plain_json_unchanged(tmp_path: Path) -> None:
    """Ordinary payloads round-trip through the plain JSON.parse fast path.

    Args:
        tmp_path: Pytest temporary directory.
    """
    payload = json.dumps({"delta": {"state": {"a": 1, "b": [None, True, "x"]}}})

    (result,) = _parse_json([payload], tmp_path)

    assert result == {"ok": {"delta": {"state": {"a": 1, "b": [None, True, "x"]}}}}


def test_non_finite_tokens_inside_strings_are_preserved(tmp_path: Path) -> None:
    """Rewriting bare tokens must not corrupt string values that contain them.

    Args:
        tmp_path: Pytest temporary directory.
    """
    payload = '{"text": "NaN and Infinity and \\"-Infinity\\"", "value": NaN}'

    (result,) = _parse_json([payload], tmp_path)

    assert result == {
        "ok": {
            "text": 'NaN and Infinity and "-Infinity"',
            "value": {"nonFinite": "NaN"},
        }
    }


def test_raises_on_unparseable_payload(tmp_path: Path) -> None:
    """A truncated payload raises so streaming callers can wait for more data.

    The upload helper parses each partial response chunk as it arrives and
    relies on the parse failing until the chunk is complete.

    Args:
        tmp_path: Pytest temporary directory.
    """
    (result,) = _parse_json(['{"delta": {"state": NaN'], tmp_path)

    assert "error" in result
