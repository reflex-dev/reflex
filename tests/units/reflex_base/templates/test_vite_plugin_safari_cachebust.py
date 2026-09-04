"""Tests for the Safari cache-busting Vite plugin shipped in the web template."""

import json
import re
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

# Drives the plugin's middleware with a fake request/response and prints every
# body fragment handed to the underlying ``res.write``/``res.end`` so the python
# side can check both the final document and how it was streamed.
DRIVER = """
import { pathToFileURL } from "node:url";
const plugin = (await import(pathToFileURL(process.argv[2]).href)).default;
const { chunks, userAgent } = JSON.parse(process.argv[3]);
console.debug = () => {};
let middleware;
plugin().configureServer({ middlewares: { use: (m) => (middleware = m) } });
const req = { url: "/", headers: { "user-agent": userAgent, accept: "text/html" } };
const writes = [];
const headers = {};
const res = {
  setHeader(name, value) { headers[name] = value; },
  write(chunk) { writes.push(String(chunk)); return true; },
  end(chunk) {
    const end = chunk === undefined ? null : String(chunk);
    process.stdout.write(JSON.stringify({ writes, end, headers }));
  },
};
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
"""


def _run_plugin(
    chunks: list[tuple[str, str]], tmp_path: Path, user_agent: str = SAFARI_UA
) -> dict:
    """Send the given chunks through the plugin middleware in node.

    Args:
        chunks: ``(kind, text)`` pairs written to the response in order.
        tmp_path: Directory used to write the driver script.
        user_agent: The request user agent.

    Returns:
        The recorded ``writes``, ``end`` body and response ``headers``.
    """
    driver = tmp_path / "driver.mjs"
    driver.write_text(DRIVER)
    return json.loads(
        subprocess.run(
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
    )


def _body(result: dict) -> str:
    """Join everything the plugin sent into the final document.

    Args:
        result: The driver output.

    Returns:
        The full response body.
    """
    return "".join(result["writes"]) + (result["end"] or "")


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
    body = _body(_run_plugin([(kind, HTML)], tmp_path))
    assert body.startswith("<!doctype html>")
    assert 'href="/app.js?__reflex_ts=' in body
    assert body.endswith("<p>ok</p>")


def test_multibyte_character_split_across_chunks(tmp_path: Path):
    """A UTF-8 sequence spanning two chunks is decoded intact.

    Args:
        tmp_path: Pytest temporary directory.
    """
    raw = list("<p>é</p>".encode())
    result = _run_plugin(
        [("bytes", json.dumps(raw[:4])), ("bytes", json.dumps(raw[4:]))], tmp_path
    )
    assert _body(result) == "<p>é</p>"


def test_streams_and_rewrites_across_chunk_boundaries(tmp_path: Path):
    """Chunks stream out as they arrive, even when a tag or href is split.

    The document is cut inside a ``<link>`` tag and inside an href used by a
    later ESM import; both must still be rewritten with one shared timestamp.

    Args:
        tmp_path: Pytest temporary directory.
    """
    chunks = [
        '<!doctype html><head><link rel="modulepreload" href="/app/ro',
        (
            'ot.jsx"><link rel="modulepreload" href="/app/entry.client.js">'
            '</head><body><div>content</div><script type="module">import "/app/entry.cl'
        ),
        'ient.js"; import * as r from "/app/root.jsx";</script></body></html>',
    ]
    result = _run_plugin([("uint8array", c) for c in chunks], tmp_path)
    body = _body(result)
    timestamps = set(re.findall(r"__reflex_ts=(\d+)", body))
    assert len(timestamps) == 1
    ts = timestamps.pop()
    assert body == (
        '<!doctype html><head><link rel="modulepreload" href="/app/root.jsx'
        f'?__reflex_ts={ts}"><link rel="modulepreload" href="/app/entry.client.js'
        f'?__reflex_ts={ts}"></head><body><div>content</div><script type="module">'
        f'import "/app/entry.client.js?__reflex_ts={ts}"; import * as r from '
        f'"/app/root.jsx?__reflex_ts={ts}";</script></body></html>'
    )
    # Every chunk was sent as it arrived, holding back only the partial tag/href.
    assert len(result["writes"]) == len(chunks)
    assert result["writes"][0] == "<!doctype html><head>"
    assert "<div>content</div>" in result["writes"][1]
    assert result["end"] == ""


def test_href_with_query_and_external_links(tmp_path: Path):
    """Existing query strings get ``&`` and external hrefs are left alone.

    Args:
        tmp_path: Pytest temporary directory.
    """
    html = (
        '<link rel="modulepreload" href="/a.js?v=1">'
        '<link rel="modulepreload" href="https://cdn.example/b.js">'
        '<script>import("/a.js?v=1")</script>'
    )
    body = _body(_run_plugin([("string", html)], tmp_path))
    assert body.count("/a.js?v=1&__reflex_ts=") == 2
    assert 'href="https://cdn.example/b.js"' in body


def test_non_safari_passthrough(tmp_path: Path):
    """Non-Safari browsers get the response untouched.

    Args:
        tmp_path: Pytest temporary directory.
    """
    result = _run_plugin(
        [("uint8array", HTML)],
        tmp_path,
        user_agent="Mozilla/5.0 Chrome/120 Safari/537.36",
    )
    assert "x-modified-by" not in result["headers"]
    assert result["end"] is None
    assert len(result["writes"]) == 1
