"""Deploy has to say something true to a workflow-only project.

``reflex workflows init`` writes one module and deliberately no
``rxconfig.py`` -- there is no frontend to configure, which is the whole
point of the workflow-only path. Deploy's generic complaint about a missing
config then tells that reader to run ``reflex init`` and start a new project,
which for them means scaffolding the web app they specifically did not want.
"""

from pathlib import Path

import pytest
from click.exceptions import Exit

from reflex.reflex import _refuse_workflow_only_deploy

WORKFLOW_MODULE = """
import reflex as rx
from reflex_base.workflow import WorkflowConfig, manual


class Flow(rx.State):
    __workflow__ = WorkflowConfig(id="deployguard.flow")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def start(self):
        return rx.complete(result=None)
"""


def test_a_workflow_only_project_is_refused_with_something_actionable(
    tmp_path, monkeypatch, capsys
):
    """Name the module, say why, and give the command that does work.

    Args:
        tmp_path: The project directory.
        monkeypatch: Used to enter that directory.
        capsys: Captures the console output.
    """
    (tmp_path / "workflows.py").write_text(WORKFLOW_MODULE)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(Exit):
        _refuse_workflow_only_deploy()
    captured = capsys.readouterr()
    # console.error goes to stderr; Rich also wraps, so flatten both.
    output = " ".join((captured.out + captured.err).split())
    assert "workflows.py" in output
    assert "reflex workflows worker" in output
    assert "reflex init" not in output, (
        "telling a workflow user to start a new project is the bug being fixed"
    )


def test_a_reflex_app_is_left_alone(tmp_path, monkeypatch):
    """A real app deploys as it always did, workflows or not.

    Args:
        tmp_path: The project directory.
        monkeypatch: Used to enter that directory.
    """
    (tmp_path / "rxconfig.py").write_text("import reflex as rx\n")
    (tmp_path / "workflows.py").write_text(WORKFLOW_MODULE)
    monkeypatch.chdir(tmp_path)
    _refuse_workflow_only_deploy()


def test_a_directory_with_no_workflows_is_left_alone(tmp_path, monkeypatch):
    """Someone in the wrong directory still gets the ordinary message.

    Args:
        tmp_path: The empty directory.
        monkeypatch: Used to enter it.
    """
    (tmp_path / "notes.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    _refuse_workflow_only_deploy()


def test_an_unreadable_file_does_not_break_the_check(tmp_path, monkeypatch):
    """A binary or badly encoded .py must not crash deploy before it starts.

    Args:
        tmp_path: The project directory.
        monkeypatch: Used to enter it.
    """
    Path(tmp_path / "broken.py").write_bytes(b"\xff\xfe\x00binary")
    monkeypatch.chdir(tmp_path)
    _refuse_workflow_only_deploy()
