"""Tests for `reflex workflows dev`, the foreground build loop.

Two things make this command usable rather than merely correct. It has to
print as it goes -- a durable run spends most of its life waiting, and a
terminal that shows nothing is indistinguishable from one that is stuck --
and it has to offer a way through a timer, because a workflow that sleeps for
a day would otherwise take a day to see run to the end.

Both are properties of a live process, so these drive the real CLI in a
subprocess and read its output as it arrives.
"""

import subprocess
import sys
import threading
import time

SLEEPY = '''
import reflex as rx


class Sleepy(rx.State):
    __workflow__ = rx.WorkflowConfig(id="dev.sleepy")
    order: str = ""

    @rx.event(durable=True, trigger=rx.manual(), effect="none")
    def start(self, order: str):
        """Charge, then wait a day.

        Args:
            order: The order being charged.

        Returns:
            The next step, due tomorrow.
        """
        self.order = order
        return rx.after("1d", Sleepy.follow_up)

    @rx.event(durable=True, effect="none")
    def follow_up(self):
        """Follow up a day later.

        Returns:
            Completion.
        """
        return rx.complete(result={"order": self.order})
'''

RUNNER = "from reflex.workflow.cli import workflows; workflows()"


def _dev_command(module, database, *extra: str) -> list[str]:
    """Build the argv that runs the dev command in a child process.

    Args:
        module: Path to the workflow module.
        database: Path to the SQLite store to use.
        extra: Extra flags for the command.

    Returns:
        The argv list.
    """
    return [
        sys.executable,
        "-c",
        RUNNER,
        "dev",
        str(module),
        "Sleepy.start",
        "--arg",
        "order=ord-1",
        "-d",
        str(database),
        *extra,
    ]


def test_dev_fast_forwards_a_timer_instead_of_waiting_for_it(tmp_path):
    """--fast-forward runs a workflow that sleeps for a day in seconds."""
    module = tmp_path / "sleepy.py"
    module.write_text(SLEEPY)
    result = subprocess.run(
        _dev_command(module, tmp_path / "ff.db", "--fast-forward"),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "fast-forward" in result.stdout
    assert "follow_up" in result.stdout
    assert "Run COMPLETED" in result.stdout
    assert "ord-1" in result.stdout


def test_dev_reports_a_sleeping_run_while_it_is_still_running(tmp_path):
    """Output reaches a pipe as it happens, and names when the run wakes.

    Without an explicit flush this prints nothing until the process exits,
    which for a run that sleeps for a day is never. The reader runs in a
    thread because the interesting output arrives while the command is still
    going; killing the process ends the read.
    """
    module = tmp_path / "sleepy_live.py"
    module.write_text(SLEEPY)
    process = subprocess.Popen(
        _dev_command(module, tmp_path / "live.db"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    seen: list[str] = []

    def drain() -> None:
        """Collect the command's output until the pipe closes."""
        assert process.stdout is not None
        for line in process.stdout:
            seen.append(line)

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if "--fast-forward" in "".join(seen):
                break
            time.sleep(0.2)
    finally:
        process.kill()
        process.wait(timeout=30)
        reader.join(timeout=30)

    output = "".join(seen)
    assert "run_admitted" in output, output
    assert "sleeps until" in output, output
    assert "--fast-forward" in output, output
