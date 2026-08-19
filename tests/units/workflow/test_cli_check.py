"""Tests for `reflex workflows check`, the generation-loop validator.

A tool that writes workflow code needs a way to find out whether the code
holds up before anything runs it. The command compiles every workflow class
in a module through the same rules registration applies, and its errors are
the compiler's teaching messages, so a generator can read them and repair its
output.
"""

import json
import sys

from click.testing import CliRunner

from reflex.workflow.cli import workflows

VALID = '''
import reflex as rx


class Greeter(rx.State):
    __workflow__ = rx.WorkflowConfig(id="check.greeter")
    name: str = ""

    @rx.event(durable=True, trigger=rx.manual(), effect="none")
    def start(self, name: str):
        """Greet.

        Args:
            name: Who to greet.

        Returns:
            Completion.
        """
        self.name = name
        return rx.complete(result={"hello": name})
'''

BROKEN = '''
import reflex as rx


class Broken(rx.State):
    __workflow__ = rx.WorkflowConfig(id="check.broken")

    @rx.event(durable=True, trigger=rx.manual(), effect="none")
    def start(self):
        """Call a sibling inline, which the compiler rejects."""
        self.finish()

    @rx.event(durable=True, effect="none")
    def finish(self):
        """Finish."""
'''

DUPLICATED = '''
import reflex as rx


class First(rx.State):
    __workflow__ = rx.WorkflowConfig(id="check.same")

    @rx.event(durable=True, trigger=rx.manual(), effect="none")
    def go(self):
        """Go."""


class Second(rx.State):
    __workflow__ = rx.WorkflowConfig(id="check.same")

    @rx.event(durable=True, trigger=rx.manual(), effect="none")
    def go(self):
        """Go."""
'''


def test_a_valid_module_passes(tmp_path, forked_registration_context):
    """Every compiling workflow is listed with its id, and the exit is clean."""
    module = tmp_path / "flows_ok.py"
    module.write_text(VALID)
    result = CliRunner().invoke(workflows, ["check", str(module)])
    assert result.exit_code == 0, result.output
    assert "check.greeter" in result.output


def test_a_compile_error_names_the_fix(tmp_path, forked_registration_context):
    """The generator reads the same teaching message the compiler raises."""
    module = tmp_path / "flows_bad.py"
    module.write_text(BROKEN)
    result = CliRunner().invoke(workflows, ["check", str(module)])
    assert result.exit_code == 1
    assert "runs it inline" in result.output
    assert "Broken.finish" in result.output


def test_duplicate_ids_across_classes_fail(tmp_path, forked_registration_context):
    """Two classes claiming one id would collide at registration; say so now."""
    module = tmp_path / "flows_dupe.py"
    module.write_text(DUPLICATED)
    result = CliRunner().invoke(workflows, ["check", str(module)])
    assert result.exit_code == 1
    assert "also declared" in result.output


def test_json_output_is_machine_readable(tmp_path, forked_registration_context):
    """A generation loop consumes the report without scraping text."""
    module = tmp_path / "flows_mixed.py"
    module.write_text(VALID + BROKEN.replace("import reflex as rx", ""))
    result = CliRunner().invoke(workflows, ["check", str(module), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    by_class = {entry["class"]: entry for entry in payload["workflows"]}
    assert by_class["Greeter"]["ok"] is True
    assert by_class["Greeter"]["workflow_id"] == "check.greeter"
    assert by_class["Broken"]["ok"] is False
    assert "inline" in by_class["Broken"]["error"]


def test_a_module_with_no_workflows_fails(tmp_path, forked_registration_context):
    """Producing nothing is a failure a generator must hear about."""
    module = tmp_path / "flows_empty.py"
    module.write_text("x = 1\n")
    result = CliRunner().invoke(workflows, ["check", str(module)])
    assert result.exit_code == 1
    assert "No workflow classes" in result.output


def test_a_missing_target_fails_cleanly(tmp_path, forked_registration_context):
    """A bad path is a named error, not a traceback."""
    result = CliRunner().invoke(
        workflows, ["check", str(tmp_path / "nope.py"), "--json"]
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False


def test_a_dotted_module_resolves_from_the_project_root(
    tmp_path, monkeypatch, forked_registration_context
):
    """`reflex workflows check myapp.flows` works from the project's own root.

    The console script's sys.path does not include the working directory the
    way `python -m` does, so without help the dotted form failed with "No
    module named", indistinguishable from a typo.
    """
    package = tmp_path / "myflows"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "orders.py").write_text(VALID)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.path", [p for p in sys.path if p != str(tmp_path)])

    result = CliRunner().invoke(workflows, ["check", "myflows.orders"])
    assert result.exit_code == 0, result.output
    assert "check.greeter" in result.output


WORKER_FLOW = '''
import reflex as rx

class Batch(rx.State):
    __workflow__ = rx.WorkflowConfig(id="worker.batch")
    label: str = ""

    @rx.event(durable=True, trigger=rx.manual(), effect="none")
    def go(self, label: str):
        """Record the label.

        Args:
            label: What to record.

        Returns:
            Completion.
        """
        self.label = label
        return rx.complete(result={"label": label})
'''


def test_the_worker_refuses_a_module_with_no_workflows(
    tmp_path, forked_registration_context
):
    """Starting a worker that would serve nothing is an error, not a hang.

    A process that sits there having silently loaded zero workflows is the
    worst failure mode for a background worker: it looks healthy forever.
    """
    module = tmp_path / "empty.py"
    module.write_text("x = 1\n")
    result = CliRunner().invoke(workflows, ["worker", str(module)])
    assert result.exit_code == 1
    assert "No workflow classes" in result.output


def test_the_worker_refuses_an_unloadable_target(tmp_path, forked_registration_context):
    """A bad path is named, not raised as a traceback."""
    result = CliRunner().invoke(workflows, ["worker", str(tmp_path / "nope.py")])
    assert result.exit_code == 1
    assert "Could not load" in result.output


def test_the_worker_names_a_compile_error(tmp_path, forked_registration_context):
    """A workflow that does not compile stops the worker with the reason.

    Starting a worker is the moment a deployment finds out its code is wrong.
    A traceback there names the compiler; the compiler's own message names the
    fix, which is what the operator reading the logs needs.
    """
    module = tmp_path / "broken_worker.py"
    module.write_text(BROKEN)
    result = CliRunner().invoke(workflows, ["worker", str(module)])
    assert result.exit_code == 1
    assert "runs it inline" in result.output
