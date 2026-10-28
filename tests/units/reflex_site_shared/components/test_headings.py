"""Tests for the shared docs heading permalinks."""

import json
import shutil
import subprocess
from collections.abc import Iterator
from typing import Any

import pytest
from reflex_site_shared.components.blocks.headings import HeadingLink

import reflex as rx

NODE = shutil.which("node")
ROUTER_URL = str(rx.State.router.url._original)


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
        location: The URL the frontend last reported to the backend.

    Returns:
        The permalink the browser would open.
    """
    assert NODE is not None
    scheme, rest = location.split("://", 1)
    netloc, _, after = rest.partition("/")
    path, _, fragment = ("/" + after).partition("#")
    url = {
        "scheme": scheme,
        "netloc": netloc,
        "origin": f"{scheme}://{netloc}",
        "path": path,
        "query": "",
        "query_parameters": {},
        "fragment": fragment,
        "href": location,
    }
    script = (
        f"const {ROUTER_URL.split('.')[0]} = {{{ROUTER_URL.split('.')[1]}: {json.dumps(url)}}};"
        "const slugifyMixedTextHastNode = (text) => text.toLowerCase().split(' ').join('-');"
        f"process.stdout.write({expression});"
    )
    return subprocess.run(
        [NODE, "-e", script], capture_output=True, text=True, check=True
    ).stdout


@pytest.mark.skipif(NODE is None, reason="node is required to evaluate the permalink")
@pytest.mark.parametrize(
    "location",
    [
        "https://reflex.dev/docs/vars/computed-vars/",
        "https://reflex.dev/docs/vars/computed-vars/#computed-vars",
        "https://reflex.dev/docs/vars/computed-vars/#computed-vars#cached-vars",
    ],
)
def test_permalink_replaces_the_current_fragment(location):
    """A heading's permalink keeps only its own fragment, whatever the URL holds."""
    href = _destination(HeadingLink.create("Cached Vars", "h2"))
    assert (
        _evaluate(href, location)
        == "https://reflex.dev/docs/vars/computed-vars/#cached-vars"
    )
