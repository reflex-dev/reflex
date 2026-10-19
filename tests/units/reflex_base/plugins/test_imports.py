"""Import behavior tests for the Reflex plugin package."""

import json
import subprocess
import sys

import reflex_base.plugins as plugins


def test_plugin_package_keeps_compiler_lazy():
    """Importing the plugin base package does not load compiler components."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, sys; import reflex_base.plugins; "
                "print(json.dumps(sorted(name for name in sys.modules "
                "if name.startswith(('reflex_base.plugins.compiler', "
                "'reflex_base.components')))))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == []


def test_plugin_package_preserves_submodule_attributes():
    """Submodules exposed by the former eager imports remain available lazily."""
    for name in (
        "_screenshot",
        "base",
        "compiler",
        "embed",
        "shared_tailwind",
        "sitemap",
        "tailwind_v3",
        "tailwind_v4",
    ):
        module = getattr(plugins, name)
        assert module.__name__ == f"reflex_base.plugins.{name}"
