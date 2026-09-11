"""Tests for the `reflex deploy` command hosted in reflex_cli.v2.deploy."""

import ast
import inspect
import subprocess
import sys
from unittest import mock

import click.testing
import pytest
from pytest_mock import MockFixture
from reflex_base.constants import LogLevel
from reflex_cli.v2.deploy import deploy

from reflex import hosting
from reflex.reflex import _LazyCommand, cli

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
    command = cli.commands["deploy"]

    assert isinstance(command, _LazyCommand)
    assert command._resolve() is deploy


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


def test_deploy_interactive_spellings_are_pinned():
    """The exact spellings `--interactive` answers to, including the `-i` alias.

    Adopting the shared option brought `-i` with it, which the parameter-name
    check above cannot see: it compares names, and the name did not move. A
    later edit to the shared option would change what `reflex deploy` accepts
    on the command line, so what it accepts is pinned here rather than left to
    be noticed by whoever's script stops working.
    """
    interactive = next(param for param in deploy.params if param.name == "interactive")

    assert set(interactive.opts) == {"--interactive", "-i"}
    assert set(interactive.secondary_opts) == {"--no-interactive"}


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


@pytest.fixture
def driven(mocker: MockFixture) -> mock.MagicMock:
    """Stub everything the deploy body reaches for beyond the flags.

    Args:
        mocker: The pytest-mock fixture.

    Returns:
        The mock standing in for the hosting CLI's own deploy.
    """
    mocker.patch("reflex_cli.v2.deployments.check_version")
    mocker.patch("reflex_cli.utils.dependency.check_requirements")
    mocker.patch(
        "reflex.hosting.prepare_deploy",
        return_value=hosting.DeployPrep(
            app_name="app", loglevel=LogLevel.INFO, ssr=True
        ),
    )
    return mocker.patch("reflex_cli.v2.cli.deploy")


@pytest.mark.parametrize(
    ("argv", "tty", "expected"),
    [
        ([], False, False),
        ([], True, True),
        (["--interactive"], False, True),
        (["-i"], False, True),
        (["--no-interactive"], True, False),
    ],
)
def test_deploy_interactive_follows_the_terminal(
    mocker: MockFixture,
    driven: mock.MagicMock,
    argv: list[str],
    tty: bool,
    expected: bool,
):
    """`reflex deploy` resolves --interactive the way every cloud command does.

    A deploy off a TTY prompts for a project, a provider and a browser login,
    so inheriting the shared default is what keeps it from hanging in CI.

    Args:
        mocker: The pytest-mock fixture.
        driven: The stubbed hosting CLI deploy.
        argv: The arguments passed on the command line.
        tty: Whether stdout is a terminal.
        expected: The interactive value the command should resolve to.
    """
    mocker.patch("reflex_cli.utils.output.stdout_is_tty", return_value=tty)

    result = click.testing.CliRunner().invoke(deploy, argv)

    assert result.exit_code == 0, result.output
    assert driven.call_args.kwargs["interactive"] is expected


@pytest.mark.usefixtures("driven")
def test_deploy_off_a_terminal_does_not_check_requirements(mocker: MockFixture):
    """The requirements check prompts, so it goes with the prompts.

    Args:
        mocker: The pytest-mock fixture.
    """
    mocker.patch("reflex_cli.utils.output.stdout_is_tty", return_value=False)
    check = mocker.patch("reflex_cli.utils.dependency.check_requirements")

    result = click.testing.CliRunner().invoke(deploy, [])

    assert result.exit_code == 0, result.output
    check.assert_not_called()
