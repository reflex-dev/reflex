"""Import-boundary tests for the public documentation API."""

import subprocess
import sys


def test_template_and_public_docs_api_import_together():
    """Keep the public docs models independent from the template module."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from reflex_site_shared.templates.docs import docs_layout_shell; "
                "from reflex_site_shared.docs import ("
                "DocsLayoutConfig, docs_sidebar_category, docs_sidebar_group); "
                "assert callable(docs_layout_shell); "
                "assert callable(docs_sidebar_category); "
                "assert callable(docs_sidebar_group); "
                "assert DocsLayoutConfig().site_title == 'Docs'"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
