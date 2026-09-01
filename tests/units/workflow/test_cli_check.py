"""Tests for `reflex workflows check`, the generation-loop validator.

A tool that writes workflow code needs a way to find out whether the code
holds up before anything runs it. The command compiles every workflow class
in a module through the same rules registration applies, and its errors are
the compiler's teaching messages, so a generator can read them and repair its
output.
"""

import json
import sys
from pathlib import Path

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


HOOKED = '''
import reflex as rx

class Hooked(rx.State):
    __workflow__ = rx.WorkflowConfig(id="check.hooked")

    @rx.event(
        durable=True,
        effect="none",
        trigger=rx.webhook(
            "orders",
            verify=rx.hmac_signature(secret_env="X_SECRET", header="X-Sig"),
        ),
    )
    def on_hook(self, payload: dict):
        """Handle a delivery.

        Args:
            payload: The delivered body.
        """
'''


def test_webhook_roots_are_named_for_the_worker(forked_registration_context):
    """A worker serves no HTTP, so it must say what it cannot start.

    Without this the symptom is a workflow that never runs beside a worker
    that looks entirely healthy -- nothing tells the operator that the process
    they are watching was never the one meant to receive the request.
    """
    from reflex_base.workflow import WorkflowConfig, hmac_signature, manual, webhook

    import reflex as rx
    from reflex.workflow.cli import webhook_root_names
    from reflex.workflow.definition import compile_workflow

    class Mixed(rx.State):
        __workflow__ = WorkflowConfig(id="check.mixed")

        @rx.event(
            durable=True,
            effect="none",
            trigger=webhook(
                "orders",
                verify=hmac_signature(secret_env="X_SECRET", header="X-Sig"),
            ),
        )
        def on_hook(self, payload: dict):
            """Handle a delivery.

            Args:
                payload: The delivered body.
            """

        @rx.event(durable=True, trigger=manual(), effect="none")
        def by_hand(self):
            """Startable anywhere."""

    names = webhook_root_names([compile_workflow(Mixed)])
    assert names == ["check.mixed.on_hook"], names


def test_init_writes_a_workflow_that_compiles(tmp_path, forked_registration_context):
    """The scaffold must be correct code, not a sketch.

    It is the first thing a new developer runs, and the commands it prints
    are the next two. A scaffold that does not compile teaches the engine's
    rules by failing at them.
    """
    from reflex.workflow.cli import workflows as group

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        written = runner.invoke(group, ["init", "orders"])
        assert written.exit_code == 0, written.output
        assert "reflex workflows dev orders.py Orders.start" in written.output

        # The generated module passes the same compiler the app applies.
        checked = runner.invoke(group, ["check", "orders.py", "--json"])
        assert checked.exit_code == 0, checked.output
        payload = json.loads(checked.output)
        assert payload["ok"] is True
        assert payload["workflows"][0]["workflow_id"] == "orders.orders"

        # A second init does not quietly overwrite the first.
        again = runner.invoke(group, ["init", "orders"])
        assert again.exit_code == 1
        assert "already exists" in again.output


def test_reflex_init_workflow_is_the_same_scaffold(tmp_path):
    """`reflex init --workflow` is the roadmap's spelling of `workflows init`.

    Both write the same module and print the same next steps; the app
    scaffold's template and AI options make no sense for it and are refused
    rather than ignored.
    """
    from reflex.reflex import cli

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        written = runner.invoke(cli, ["init", "--workflow", "--name", "orders"])
        assert written.exit_code == 0, written.output
        assert (Path(cwd) / "orders.py").exists()
        assert not (Path(cwd) / "rxconfig.py").exists(), "no app was scaffolded"
        assert "reflex workflows dev orders.py Orders.start" in written.output

        default = runner.invoke(cli, ["init", "--workflow"])
        assert default.exit_code == 0, default.output
        assert (Path(cwd) / "workflows.py").exists()

        refused = runner.invoke(cli, ["init", "--workflow", "--template", "blank"])
        assert refused.exit_code == 1
        assert "--template" in refused.output


TRIGGERED = '''
import reflex as rx

class Billing(rx.State):
    __workflow__ = rx.WorkflowConfig(id="check.billing")

    @rx.event(
        durable=True,
        effect="none",
        trigger=rx.webhook(
            "stripe.paid",
            verify=rx.hmac_signature(secret_env="S", header="X-Sig"),
            dedupe_by="id",
        ),
    )
    def on_paid(self, payload: dict):
        """Handle a payment.

        Args:
            payload: The delivered body.
        """

    @rx.event(durable=True, effect="none", trigger=rx.schedule("0 3 * * *"))
    def nightly(self):
        """Run nightly."""

    @rx.event(durable=True, effect="none", trigger=rx.manual())
    def by_hand(self):
        """Started from code."""
'''


def test_triggers_reports_how_each_workflow_starts(
    tmp_path, forked_registration_context
):
    """An operator can see what starts a deployment without reading its source.

    "Is the cron registered, and what URL does the provider post to" are the
    questions asked when something has not fired, and reading the code is the
    wrong answer to both.
    """
    module = tmp_path / "billing.py"
    module.write_text(TRIGGERED)
    result = CliRunner().invoke(workflows, ["triggers", str(module), "--json"])
    assert result.exit_code == 0, result.output
    rows = {entry["handler"]: entry for entry in json.loads(result.output)}

    assert rows["on_paid"]["kind"] == "webhook"
    assert rows["on_paid"]["path"] == "/_workflow/webhook/stripe.paid"
    assert rows["on_paid"]["verified"] is True
    assert rows["on_paid"]["dedupe_by"] == "id"

    assert rows["nightly"]["kind"] == "schedule"
    assert rows["nightly"]["detail"] == "0 3 * * *"
    assert rows["nightly"]["next_fire"], "a schedule with no next occurrence"

    assert rows["by_hand"]["kind"] == "manual"


def test_triggers_flags_an_unverified_webhook(tmp_path, forked_registration_context):
    """The text view says which endpoints are open, since that is the risk."""
    module = tmp_path / "billing2.py"
    module.write_text(TRIGGERED)
    result = CliRunner().invoke(workflows, ["triggers", str(module)])
    assert result.exit_code == 0
    assert "signature verified" in result.output
    assert "POST /_workflow/webhook/stripe.paid" in result.output


HOOKED = '''
import reflex as rx


class Hooked(rx.State):
    __workflow__ = rx.WorkflowConfig(id="doctor.hooked")

    @rx.event(
        durable=True,
        effect="none",
        trigger=rx.webhook(
            "orders",
            verify=rx.hmac_signature(secret_env="DOCTOR_SECRET", header="X-Sig"),
        ),
    )
    def on_hook(self, payload: dict):
        """Take a delivery.

        Args:
            payload: The delivered body.

        Returns:
            Completion.
        """
        return rx.complete(result=payload)

    @rx.event(durable=True, effect="none", trigger=rx.schedule("0 9 * * *"))
    def nightly(self):
        """Run nightly.

        Returns:
            Completion.
        """
        return rx.complete(result=None)
'''


def test_doctor_reports_an_unset_webhook_secret(
    tmp_path, monkeypatch, forked_registration_context
):
    """A verifier whose secret is missing refuses every delivery; say so first."""
    monkeypatch.delenv("DOCTOR_SECRET", raising=False)
    module = tmp_path / "flows_hooked.py"
    module.write_text(HOOKED)
    result = CliRunner().invoke(
        workflows, ["doctor", str(module), "-d", str(tmp_path / "d.db")]
    )
    assert result.exit_code == 1, result.output
    assert "DOCTOR_SECRET is unset" in result.output
    assert "doctor.hooked.on_hook" in result.output


def test_doctor_passes_once_the_secret_is_set(
    tmp_path, monkeypatch, forked_registration_context
):
    """With every required secret present the deployment is ready to serve."""
    monkeypatch.setenv("DOCTOR_SECRET", "shhh")
    module = tmp_path / "flows_hooked_ok.py"
    module.write_text(HOOKED)
    result = CliRunner().invoke(
        workflows, ["doctor", str(module), "-d", str(tmp_path / "d.db")]
    )
    assert result.exit_code == 0, result.output
    assert "ready to serve" in result.output


def test_doctor_notes_schedules_and_unmounted_surfaces(
    tmp_path, monkeypatch, forked_registration_context
):
    """Notes name what a deployment still has to run or configure."""
    monkeypatch.setenv("DOCTOR_SECRET", "shhh")
    monkeypatch.delenv("REFLEX_WORKFLOW_API_TOKEN", raising=False)
    module = tmp_path / "flows_hooked_notes.py"
    module.write_text(HOOKED)
    result = CliRunner().invoke(
        workflows, ["doctor", str(module), "-d", str(tmp_path / "d.db")]
    )
    assert result.exit_code == 0, result.output
    assert "0 9 * * *" in result.output
    assert "REFLEX_WORKFLOW_API_TOKEN" in result.output


UNVERIFIED = '''
import reflex as rx


class Open(rx.State):
    __workflow__ = rx.WorkflowConfig(id="doctor.open")

    @rx.event(
        durable=True,
        effect="none",
        trigger=rx.webhook(
            "payout",
            allow_unverified=True,
            unverified_reason="behind an internal load balancer",
        ),
    )
    def on_hook(self, payload: dict):
        """Take an unverified delivery.

        Args:
            payload: The delivered body.

        Returns:
            Completion.
        """
        return rx.complete(result=payload)
'''


def test_doctor_names_a_webhook_that_takes_anonymous_deliveries(
    tmp_path, forked_registration_context
):
    """Opting in protects the author; deploying is done by someone else.

    Compiling already refuses an unverified webhook unless someone passed
    allow_unverified with a reason. That is a decision made once, by whoever
    wrote it. The person deploying a year later reads this preflight instead,
    and an endpoint anyone can post runs into is exactly what it is for.

    Args:
        tmp_path: Temporary directory for the module and database.
        forked_registration_context: Isolates state registration.
    """
    module = tmp_path / "flows_open.py"
    module.write_text(UNVERIFIED)
    result = CliRunner().invoke(
        workflows, ["doctor", str(module), "-d", str(tmp_path / "d.db")]
    )
    assert result.exit_code == 0, result.output
    # Rich wraps at the terminal width, so the note arrives split across
    # lines; the reader sees one sentence and the test should too.
    flattened = " ".join(result.output.split())
    assert "unverified deliveries" in flattened
    assert "doctor.open.on_hook" in flattened
    assert "behind an internal load balancer" in flattened
