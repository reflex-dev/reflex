"""Enforce that compiling the docs does not evaluate `rx.upload`.

`Upload.is_used` is a class-level flag flipped to ``True`` whenever
``rx.upload(...)`` / ``rx.upload.root(...)`` is constructed. When the docs site
is compiled, that flag (and the on-disk marker it writes) causes the upload
HTTP endpoint to be registered. The docs site never needs upload functionality,
so any `python exec` / `python demo` / `python demo exec` / `python eval` block
that constructs an upload component is a regression — code samples for
``rx.upload`` must stay in plain ```python``` fenced blocks. The same goes for
the ``components:`` frontmatter preview lambdas rendered by the docgen pipeline.
"""

import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def routes_fixture():
    from reflex_docs.pages import routes

    yield routes


def test_compiling_docs_does_not_evaluate_upload(routes_fixture):
    """Loading the docs route tree must not flip ``Upload.is_used``."""
    from reflex_components_core.core.upload import Upload

    assert routes_fixture is not None
    assert not Upload.is_used, (
        "Compiling the docs flipped Upload.is_used = True. "
        "An rx.upload(...) call leaked into an executed block "
        "(python exec / python demo / python demo exec / python eval) "
        "or into a ``components:`` frontmatter preview lambda. "
        "Move the upload sample into a plain ```python fenced block."
    )
