"""Tests for the `reflex deploy` command hosted in reflex_cli.v2.deploy."""

import ast
import inspect
import subprocess
import sys

import click.testing
from reflex_cli.v2.deploy import deploy

from reflex.reflex import cli

EXPECTED_DEPLOY_PARAMS = {
    "app_name",
    "app_id",
    "region",
    "env",
    "vmtype",
    "min_instances",
    "max_instances",
    "hostname",
    "provider",
    "gcp_connection",
    "full_deploy",
    "strategy",
    "description",
    "interactive",
    "envfile",
    "project",
    "project_name",
    "token",
    "config_path",
    "backend_excluded_dirs",
    "ssr",
}


def test_deploy_registered_on_reflex_cli():
    """`reflex deploy` resolves to the command hosted in the hosting CLI."""
    assert cli.commands["deploy"] is deploy


def test_hosting_cli_deploy_imports_without_the_framework():
    """The deploy module imports with the reflex framework unavailable.

    `reflex` is deliberately not a dependency of reflex-hosting-cli, so anything
    the module needs at import time must come from the hosting CLI itself.
    """
    probe = """
import sys
class Blocked:
    def find_spec(self, name, path=None, target=None):
        if name == "reflex" or name.startswith("reflex."):
            raise ImportError(name)
sys.meta_path.insert(0, Blocked())
import reflex_cli.v2.deploy
print("ok")
"""
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_deploy_flag_surface_unchanged():
    """The moved command keeps the exact set of CLI parameters it shipped with."""
    param_names = {
        param.name for param in deploy.params if param.expose_value and param.name
    }
    assert param_names == EXPECTED_DEPLOY_PARAMS


def test_deploy_keeps_log_options():
    """The shared logging flags stay on the command after the cli_options move."""
    option_names = {opt for param in deploy.params for opt in param.opts}
    assert {"--loglevel", "--log-level", "--json"} <= option_names


def test_deploy_uses_only_the_supported_framework_interface():
    """The command imports the framework only through `reflex.hosting`.

    That module is the interface reflex explicitly supports for the hosting
    CLI; anything else is a reflex internal that may change without notice.
    """
    import reflex_cli.v2.deploy as deploy_module

    tree = ast.parse(inspect.getsource(deploy_module))
    framework_imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "reflex" or module.startswith("reflex."):
                framework_imports.add(module)
        elif isinstance(node, ast.Import):
            framework_imports.update(
                alias.name
                for alias in node.names
                if alias.name == "reflex" or alias.name.startswith("reflex.")
            )
    assert framework_imports == {"reflex.hosting"}


def test_deploy_help():
    """`reflex deploy --help` renders without importing the reflex runtime."""
    result = click.testing.CliRunner().invoke(cli, ["deploy", "--help"])
    assert result.exit_code == 0
    assert "Deploy the app to the Reflex hosting service." in result.output
