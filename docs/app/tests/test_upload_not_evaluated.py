"""Enforce that compiling the docs app does not evaluate `rx.upload`.

`Upload.is_used` is a class-level flag flipped to ``True`` whenever
``rx.upload(...)`` / ``rx.upload.root(...)`` is constructed. When the docs site
is compiled, that flag (and the on-disk marker it writes) causes the upload
HTTP endpoint to be registered. The docs site never needs upload functionality,
so any `python exec` / `python demo` / `python demo exec` / `python eval` block
that constructs an upload component is a regression — code samples for
``rx.upload`` must stay in plain ```python``` fenced blocks. The same goes for
the ``components:`` frontmatter preview lambdas rendered by the docgen pipeline.
"""

import subprocess
import sys


def test_compiling_docs_does_not_evaluate_upload():
    """A fresh import of the docs app must not flip ``Upload.is_used``.

    Runs in a subprocess: the flag is sticky once flipped and reflex_docs
    modules get cached in ``sys.modules`` after the first import, so checking
    in-process would only catch regressions when this test happens to run
    before any other docs test imports ``reflex_docs.pages``.
    """
    code = (
        "from reflex_components_core.core.upload import Upload\n"
        "import reflex_docs.pages  # builds all routes; renders every doc\n"
        "import sys\n"
        "sys.exit(1 if Upload.is_used else 0)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Compiling the docs flipped Upload.is_used = True. "
        "An rx.upload(...) call leaked into an executed block "
        "(python exec / python demo / python demo exec / python eval) "
        "or into a ``components:`` frontmatter preview lambda. "
        "Move the upload sample into a plain ```python fenced block.\n\n"
        f"subprocess stderr:\n{result.stderr}"
    )
