"""Tests for reflex_bench.collectors.cgroup."""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import psutil
import pytest
from reflex_bench.collectors import cgroup

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX processes")

SCOPE_FILES = {
    "memory.peak": "734003200\n",
    "memory.current": "536870912\n",
    "memory.stat": "anon 402653184\nfile 100663296\nkernel 8388608\nsock 0\n",
    "memory.events": "low 0\nhigh 0\nmax 3\noom 1\noom_kill 1\noom_group_kill 0\n",
    "cpu.stat": (
        "usage_usec 2500000\nuser_usec 2000000\nsystem_usec 500000\n"
        "nr_periods 0\nnr_throttled 0\nthrottled_usec 0\n"
    ),
}


def _scope_dir(root: Path, relative: str, peak_mode: int = 0o444) -> Path:
    """Create a cgroup directory with the files a scope has.

    Returns:
        The directory.
    """
    directory = root / relative.lstrip("/")
    directory.mkdir(parents=True)
    for name, content in SCOPE_FILES.items():
        (directory / name).write_text(content, encoding="utf-8")
    (directory / "memory.peak").chmod(peak_mode)
    return directory


@pytest.fixture
def linux(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """Make the probe see a cgroup v2 Linux host with systemd-run; nothing runs.

    Yields:
        The fake cgroup v2 root.
    """
    root = tmp_path / "cgroup"
    root.mkdir()
    (root / "cgroup.controllers").write_text(
        "cpuset cpu io memory pids\n", encoding="utf-8"
    )
    monkeypatch.setattr(cgroup, "_linux", lambda: True)
    monkeypatch.setattr(cgroup, "_cgroup2_root", lambda: root)
    monkeypatch.setattr(cgroup, "_kernel", lambda: (6, 12))
    monkeypatch.setattr(cgroup.shutil, "which", lambda name: f"/usr/bin/{name}")
    cgroup.probe.cache_clear()
    yield root
    cgroup.probe.cache_clear()


def _runner(
    results: dict[str, tuple[bool, str]],
) -> Callable[[Sequence[str]], tuple[bool, str]]:
    """Answer probe commands by their leading words, recording nothing else.

    Returns:
        A stand-in for ``cgroup._run``.
    """

    def run(argv: Sequence[str]) -> tuple[bool, str]:
        for prefix, result in results.items():
            if " ".join(argv).startswith(prefix):
                return result
        msg = f"unexpected probe {argv}"
        raise AssertionError(msg)

    return run


def test_probe_prefers_the_user_manager(linux: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cgroup, "_run", _runner({"systemd-run --user": (True, "")}))
    assert cgroup.probe() == ("user", None)
    assert cgroup.CgroupScope.available() is None
    assert cgroup.status() == (True, "ok (user systemd)")


def test_probe_falls_back_to_sudo(linux: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        cgroup,
        "_run",
        _runner({
            "systemd-run --user": (False, "Failed to connect to bus: No medium found"),
            "sudo -n true": (True, ""),
            "sudo -n -E systemd-run --scope": (True, ""),
        }),
    )
    assert cgroup.probe() == ("sudo", None)
    assert cgroup.status() == (True, "ok (sudo)")


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        (
            {
                "systemd-run --user": (
                    False,
                    "Failed to connect to bus: No medium found",
                ),
                "sudo -n true": (False, "sudo: a password is required"),
            },
            (
                "no user systemd manager (Failed to connect to bus: No medium found);"
                " no passwordless sudo (sudo: a password is required)"
            ),
        ),
        (
            {
                "systemd-run --user": (
                    False,
                    "Failed to connect to bus: No medium found",
                ),
                "sudo -n true": (True, ""),
                "sudo -n -E systemd-run --scope": (
                    False,
                    "System has not been booted with systemd as init system (PID 1).",
                ),
            },
            (
                "no user systemd manager (Failed to connect to bus: No medium found);"
                " sudo systemd-run failed (System has not been booted with systemd as"
                " init system (PID 1).)"
            ),
        ),
    ],
)
def test_probe_explains_why_scopes_are_unavailable(
    linux: Path,
    monkeypatch: pytest.MonkeyPatch,
    results: dict[str, tuple[bool, str]],
    expected: str,
):
    monkeypatch.setattr(cgroup, "_run", _runner(results))
    assert cgroup.probe() == (None, expected)
    assert cgroup.CgroupScope.available() == expected
    assert cgroup.status() == (False, f"unavailable: {expected}")
    with pytest.raises(RuntimeError, match="cgroup scopes are unavailable"):
        cgroup.CgroupScope()


@pytest.mark.parametrize(
    ("patch", "reason"),
    [
        (("_linux", lambda: False), "cgroup scopes need Linux"),
        (("_cgroup2_root", lambda: None), "no cgroup v2 hierarchy is mounted"),
        (
            ("_kernel", lambda: (5, 15)),
            "memory.peak needs Linux 5.19 or later (running 5.15)",
        ),
    ],
)
def test_probe_checks_the_host_first(
    linux: Path,
    monkeypatch: pytest.MonkeyPatch,
    patch: tuple[str, Callable[[], object]],
    reason: str,
):
    monkeypatch.setattr(cgroup, *patch)
    monkeypatch.setattr(cgroup, "_run", _runner({}))
    assert cgroup.probe() == (None, reason)


def test_probe_needs_the_memory_controller(
    linux: Path, monkeypatch: pytest.MonkeyPatch
):
    (linux / "cgroup.controllers").write_text("hugetlb\n", encoding="utf-8")
    monkeypatch.setattr(cgroup, "_run", _runner({}))
    assert cgroup.probe() == (
        None,
        f"the cgroup v2 hierarchy at {linux} has no memory controller (hybrid cgroup v1 host)",
    )


def test_probe_needs_systemd_run(linux: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cgroup.shutil, "which", lambda name: None)
    monkeypatch.setattr(cgroup, "_run", _runner({}))
    assert cgroup.probe() == (None, "systemd-run not found")


def test_cgroup2_root_from_mounts(tmp_path: Path):
    mounts = tmp_path / "mounts"
    mounts.write_text(
        "tmpfs /sys/fs/cgroup tmpfs rw,relatime,mode=755 0 0\n"
        "cgroup /sys/fs/cgroup/memory cgroup rw,relatime,memory 0 0\n"
        "cgroup2 /sys/fs/cgroup/unified cgroup2 rw,relatime 0 0\n",
        encoding="utf-8",
    )
    assert cgroup._cgroup2_root(mounts) == Path("/sys/fs/cgroup/unified")
    mounts.write_text("proc /proc proc rw 0 0\n", encoding="utf-8")
    assert cgroup._cgroup2_root(mounts) is None


def _unit(argv: list[str]) -> str:
    (unit,) = [arg.removeprefix("--unit=") for arg in argv if arg.startswith("--unit=")]
    return unit


def test_wrap_for_the_user_manager():
    scope = cgroup.CgroupScope(mode="user")
    argv = scope.wrap(["python", "-m", "reflex", "compile"])
    unit = _unit(argv)
    assert unit == scope.unit
    assert unit.startswith("reflex-bench-")
    assert argv == [
        "systemd-run", "--user", "--scope", "--quiet", "--collect", f"--unit={unit}",
        "-p", "MemoryAccounting=yes", "-p", "CPUAccounting=yes",
        "--", "python", "-m", "reflex", "compile",
    ]  # fmt: skip
    # Every wrap starts a new scope.
    assert _unit(scope.wrap(["true"])) != unit


@pytest.fixture
def oom_policy(monkeypatch: pytest.MonkeyPatch) -> Callable[[bool], None]:
    """Set whether the host's systemd accepts ``OOMPolicy=`` on scopes.

    Returns:
        A setter.
    """

    def set_supported(supported: bool) -> None:
        monkeypatch.setattr(cgroup, "oom_policy_supported", lambda mode: supported)

    return set_supported


@posix_only
def test_wrap_with_sudo_keeps_the_user_and_path(oom_policy: Callable[[bool], None]):
    oom_policy(True)
    scope = cgroup.CgroupScope(mode="sudo", limit_bytes=512 * 1024**2)
    argv = scope.wrap(["python", "-m", "reflex"], env={"PATH": "/venv/bin:/usr/bin"})
    assert argv == [
        "sudo", "-n", "-E", "systemd-run", "--scope", "--quiet", "--collect",
        f"--unit={scope.unit}", f"--uid={os.getuid()}", f"--gid={os.getgid()}",
        "--setenv=PATH=/venv/bin:/usr/bin",
        "-p", "MemoryAccounting=yes", "-p", "CPUAccounting=yes",
        "-p", "MemoryMax=536870912", "-p", "MemorySwapMax=0",
        "-p", "OOMPolicy=continue",
        "--", "python", "-m", "reflex",
    ]  # fmt: skip


def test_wrap_leaves_oom_policy_out_where_systemd_lacks_it(
    oom_policy: Callable[[bool], None],
):
    oom_policy(False)
    argv = cgroup.CgroupScope(mode="user", limit_bytes=1000).wrap(["x"])
    assert "MemoryMax=1000" in argv
    assert not any(arg.startswith("OOMPolicy") for arg in argv)


def test_wrap_can_allow_swap_under_a_limit(oom_policy: Callable[[bool], None]):
    oom_policy(True)
    argv = cgroup.CgroupScope(mode="user", limit_bytes=1000, swap_max=None).wrap(["x"])
    assert "MemoryMax=1000" in argv
    assert not any(arg.startswith("MemorySwapMax") for arg in argv)


@pytest.mark.parametrize(
    ("result", "supported"),
    [((True, ""), True), ((False, "Unknown assignment: OOMPolicy=continue"), False)],
)
def test_oom_policy_supported_tries_it(
    monkeypatch: pytest.MonkeyPatch, result: tuple[bool, str], supported: bool
):
    cgroup.oom_policy_supported.cache_clear()
    seen: list[Sequence[str]] = []

    def run(argv: Sequence[str]) -> tuple[bool, str]:
        seen.append(argv)
        return result

    monkeypatch.setattr(cgroup, "_run", run)
    try:
        assert cgroup.oom_policy_supported("user") is supported
        assert cgroup.oom_policy_supported("user") is supported
    finally:
        cgroup.oom_policy_supported.cache_clear()
    (argv,) = seen
    assert argv[:3] == ["systemd-run", "--user", "--scope"]
    assert argv[-4:] == ["-p", "OOMPolicy=continue", "--", "true"]


@pytest.fixture
def child() -> Iterator[psutil.Process]:
    """Start a real process with a child, standing in for sudo and the command it runs.

    Yields:
        The parent; its only child is the command.
    """
    code = (
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "time.sleep(60)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", code])
    parent = psutil.Process(proc.pid)
    try:
        deadline = time.monotonic() + 30
        while not parent.children() and time.monotonic() < deadline:
            time.sleep(0.01)
        yield parent
    finally:
        for process in parent.children(recursive=True):
            with contextlib.suppress(psutil.NoSuchProcess):
                process.kill()
        proc.kill()
        proc.wait()


def _fake_proc_cgroup(proc_root: Path, pid: int, relative: str) -> None:
    (proc_root / str(pid)).mkdir(parents=True)
    (proc_root / str(pid) / "cgroup").write_text(f"0::{relative}\n", encoding="utf-8")


@posix_only
def test_attach_finds_the_scope_below_the_wrapper(
    tmp_path: Path, child: psutil.Process
):
    proc_root, cgroup_root = tmp_path / "proc", tmp_path / "cgroup"
    scope = cgroup.CgroupScope(
        mode="sudo", proc_root=proc_root, cgroup_root=cgroup_root
    )
    scope.wrap(["true"])
    relative = f"/system.slice/{scope.unit}.scope"
    directory = _scope_dir(cgroup_root, relative)
    # sudo stays in the caller's cgroup; only the command it starts enters the scope.
    _fake_proc_cgroup(proc_root, child.pid, "/user.slice/session-2.scope")
    _fake_proc_cgroup(proc_root, child.children()[0].pid, relative)
    scope.attach(child.pid, timeout=5)
    assert scope.path == directory


@posix_only
def test_attach_gives_up(tmp_path: Path, child: psutil.Process):
    scope = cgroup.CgroupScope(
        mode="user", proc_root=tmp_path / "proc", cgroup_root=tmp_path / "cgroup"
    )
    scope.wrap(["true"])
    with pytest.raises(RuntimeError, match=f"never entered scope {scope.unit}"):
        scope.attach(child.pid, timeout=0.1)


def _attached(tmp_path: Path, peak_mode: int = 0o444) -> cgroup.CgroupScope:
    scope = cgroup.CgroupScope(mode="user", cgroup_root=tmp_path)
    scope.wrap(["true"])
    scope.path = _scope_dir(tmp_path, f"/app.slice/{scope.unit}.scope", peak_mode)
    return scope


def test_read(tmp_path: Path):
    assert _attached(tmp_path).read() == cgroup.CgroupReading(
        memory_peak_bytes=734_003_200,
        memory_current_bytes=536_870_912,
        anon_bytes=402_653_184,
        file_bytes=100_663_296,
        oom=1,
        oom_kill=1,
        cpu_usage_usec=2_500_000,
        cpu_user_usec=2_000_000,
        cpu_system_usec=500_000,
        peak_reset=False,
    )


def test_read_before_attach_fails():
    with pytest.raises(RuntimeError, match="attach"):
        cgroup.CgroupScope(mode="user").read()


def test_reset_peak_on_kernels_without_it(tmp_path: Path):
    # Before Linux 6.12 memory.peak is read-only: peaks cover the whole run.
    scope = _attached(tmp_path, peak_mode=0o444)
    scope.reset_peak()
    reading = scope.read()
    assert reading.peak_reset is False
    assert reading.memory_peak_bytes == 734_003_200


def test_reset_peak_reads_through_the_reset_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # From Linux 6.12 a write resets the peak seen through that file descriptor;
    # a regular file cannot do that, so the descriptor I/O is simulated.
    scope = _attached(tmp_path, peak_mode=0o644)
    writes: list[bytes] = []
    monkeypatch.setattr(
        cgroup.os, "write", lambda fd, data: writes.append(data) or len(data)
    )
    # The first read validates the reset; later ones are the peaks since each reset.
    since_reset = iter([b"4096\n", b"8192\n", b"1024\n"])
    monkeypatch.setattr(cgroup.os, "pread", lambda fd, size, offset: next(since_reset))
    scope.reset_peak()
    first = scope.read()
    assert (first.memory_peak_bytes, first.peak_reset) == (8192, True)
    scope.reset_peak()
    assert scope.read().memory_peak_bytes == 1024
    assert writes == [b"reset\n", b"reset\n"]
    scope.close()
    whole_run = scope.read()
    assert (whole_run.memory_peak_bytes, whole_run.peak_reset) == (734_003_200, False)
