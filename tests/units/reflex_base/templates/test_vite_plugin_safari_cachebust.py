"""Tests for the Safari cache-busting Vite plugin shipped in the web template."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import reflex_base

PLUGIN_PATH = (
    Path(reflex_base.__file__).parent
    / ".templates"
    / "web"
    / "vite-plugin-safari-cachebust.js"
)

SAFARI_UA = "Mozilla/5.0 (Macintosh) AppleWebKit/605.1.15 Safari/605.1.15"

# Drives the plugin's middleware with a fake request/response and prints the
# body handed to the underlying ``res.end`` so the python side can inspect it.
DRIVER = """
import { pathToFileURL } from "node:url";
const plugin = (await import(pathToFileURL(process.argv[2]).href)).default;
const { chunks, userAgent } = JSON.parse(process.argv[3]);
console.debug = () => {};
let middleware;
plugin().configureServer({ middlewares: { use: (m) => (middleware = m) } });
const req = { url: "/", headers: { "user-agent": userAgent, accept: "text/html" } };
let body;
const res = { setHeader() {}, write() {}, end(chunk) { body = chunk; } };
middleware(req, res, () => {
  for (const [kind, text] of chunks) {
    const bytes = new TextEncoder().encode(text);
    if (kind === "string") res.write(text);
    else if (kind === "buffer") res.write(Buffer.from(bytes));
    else if (kind === "uint8array") res.write(bytes);
    else if (kind === "bytes") res.write(Buffer.from(JSON.parse(text)));
  }
  res.end();
});
process.stdout.write(String(body));
"""


def _run_plugin(
    chunks: list[tuple[str, str]], user_agent: str = SAFARI_UA, tmp_path: Path = Path()
) -> str:
    """Send the given chunks through the plugin middleware in node.

    Args:
        chunks: ``(kind, text)`` pairs written to the response in order.
        user_agent: The request user agent.
        tmp_path: Directory used to write the driver script.

    Returns:
        The response body as seen by the wrapped ``res.end``.
    """
    driver = tmp_path / "driver.mjs"
    driver.write_text(DRIVER)
    return subprocess.run(
        [
            "node",
            str(driver),
            str(PLUGIN_PATH),
            json.dumps({"chunks": chunks, "userAgent": user_agent}),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


HTML = '<!doctype html><link rel="modulepreload" href="/app.js"><p>ok</p>'

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node missing")


@pytest.mark.parametrize("kind", ["string", "buffer", "uint8array"])
def test_rewrites_modulepreload_for_any_chunk_type(kind: str, tmp_path: Path):
    """Chunks of every type the dev server may write are decoded as text.

    React Router 8 writes plain ``Uint8Array`` chunks (not ``Buffer``), which
    previously got stringified as comma-separated byte values.

    Args:
        kind: The chunk type to write.
        tmp_path: Pytest temporary directory.
    """
    body = _run_plugin([(kind, HTML)], tmp_path=tmp_path)
    assert body.startswith("<!doctype html>")
    assert 'href="/app.js?__reflex_ts=' in body
    assert body.endswith("<p>ok</p>")


def test_multibyte_character_split_across_chunks(tmp_path: Path):
    """A UTF-8 sequence spanning two chunks is decoded intact.

    Args:
        tmp_path: Pytest temporary directory.
    """
    raw = list("<p>é</p>".encode())
    body = _run_plugin(
        [("bytes", json.dumps(raw[:4])), ("bytes", json.dumps(raw[4:]))],
        tmp_path=tmp_path,
    )
    assert body == "<p>é</p>"


def test_non_safari_passthrough(tmp_path: Path):
    """Non-Safari browsers get the response untouched.

    Args:
        tmp_path: Pytest temporary directory.
    """
    body = _run_plugin(
        [("uint8array", HTML)],
        user_agent="Mozilla/5.0 Chrome/120 Safari/537.36",
        tmp_path=tmp_path,
    )
    assert body == "undefined"
