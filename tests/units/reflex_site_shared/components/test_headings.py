"""Tests for the shared docs heading permalinks."""

import json
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import reflex_base
from reflex_site_shared.components.blocks.headings import HeadingLink

import reflex as rx
from reflex.istate.data import ReflexURL, _serialize_reflex_url

NODE = shutil.which("node")
ROUTER_URL = str(rx.State.router.url._original)
STATE_JS = (
    Path(reflex_base.__file__).parent / ".templates" / "web" / "utils" / "state.js"
)
# The generated expression calls the frontend's isTrue helper; load the real one.
IS_TRUE = re.search(
    r"^export (const isTrue = .*?^};)", STATE_JS.read_text(), re.DOTALL | re.MULTILINE
)


def _destination(component: Any) -> str:
    """Return the JS expression of the permalink a heading links to.

    Args:
        component: The heading link component.

    Returns:
        The rendered destination expression.
    """

    def walk(node: Any) -> Iterator[Any]:
        yield node
        for child in node.children:
            yield from walk(child)

    destinations = [
        str(node.to)
        for node in walk(component)
        if getattr(node, "to", None) is not None
    ]
    assert len(destinations) == 1
    return destinations[0]


def _evaluate(expression: str, location: str) -> str:
    """Evaluate a permalink expression against a browser location.

    Args:
        expression: The JS expression for the permalink.
        location: The URL the frontend last reported to the backend, or an
            empty string before its first report.

    Returns:
        The permalink the browser would open.
    """
    assert NODE is not None
    url = _serialize_reflex_url(ReflexURL(location))
    state, field = ROUTER_URL.split(".")
    assert IS_TRUE is not None
    script = (
        f"{IS_TRUE[1]}"
        f"const {state} = {{{field}: {json.dumps(url)}}};"
        "const slugifyMixedTextHastNode = (text) => text.toLowerCase().split(' ').join('-');"
        f"process.stdout.write({expression});"
    )
    return subprocess.run(
        [NODE, "-e", script], capture_output=True, text=True, check=True
    ).stdout


@pytest.mark.skipif(NODE is None, reason="node is required to evaluate the permalink")
@pytest.mark.parametrize(
    ("location", "permalink"),
    [
        (
            "https://reflex.dev/docs/vars/computed-vars/",
            "https://reflex.dev/docs/vars/computed-vars/#cached-vars",
        ),
        (
            "https://reflex.dev/docs/vars/computed-vars/#computed-vars",
            "https://reflex.dev/docs/vars/computed-vars/#cached-vars",
        ),
        (
            "https://reflex.dev/docs/vars/computed-vars/#computed-vars#cached-vars",
            "https://reflex.dev/docs/vars/computed-vars/#cached-vars",
        ),
        (
            "https://reflex.dev/docs/vars/computed-vars/?tab=code#computed-vars",
            "https://reflex.dev/docs/vars/computed-vars/?tab=code#cached-vars",
        ),
        # Before the backend's first reply the reported URL is still empty.
        ("", "#cached-vars"),
    ],
)
def test_permalink_replaces_the_current_fragment(location, permalink):
    """A heading's permalink keeps only its own fragment, whatever the URL holds."""
    href = _destination(HeadingLink.create("Cached Vars", "h2"))
    assert _evaluate(href, location) == permalink
