"""Tests for reflex_bench.machine."""

from __future__ import annotations

from pathlib import Path

import pytest
from reflex_bench import machine
from reflex_bench.schema import validate

from .factories import make_doc, make_machine

CPUINFO = """\
processor\t: 0
vendor_id\t: AuthenticAMD
model\t\t: 97
model name\t: AMD Ryzen 9 7950X 16-Core Processor
flags\t\t: fpu vme de pse tsc msr
"""


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def sysroot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv(machine.PROFILE_ENV, raising=False)
    # No probing commands: the fake filesystem is the only source.
    monkeypatch.setattr(machine, "_run", lambda *cmd: None)
    _write(tmp_path, "proc/cpuinfo", CPUINFO)
    for cpu in ("cpu0", "cpu1"):
        _write(
            tmp_path,
            f"sys/devices/system/cpu/{cpu}/cpufreq/scaling_governor",
            "powersave\n",
        )
    _write(tmp_path, "sys/devices/system/cpu/intel_pstate/no_turbo", "0\n")
    _write(tmp_path, "sys/fs/cgroup/cgroup.controllers", "cpu memory\n")
    _write(tmp_path, "proc/1/cgroup", "0::/\n")
    return tmp_path


def test_collect_reads_linux_sources(sysroot: Path):
    found = machine.collect(sysroot, system="Linux", python_version="3.12.8")
    assert found["cpu_model"] == "AMD Ryzen 9 7950X 16-Core Processor"
    assert found["profile_id"].startswith("linux-")
    assert found["profile_id"].endswith("-ryzen-9-7950x-py3.12")
    assert found["governor"] == "powersave"
    assert found["turbo"] is True
    assert found["cgroup_v2"] is True
    assert found["container"] is False
    assert found["virtualized"] is None
    assert found["cpu_count"]
    assert found["ram_bytes"]
    assert set(found["tools"]) == {"bun", "node", "chromium"}
    assert validate(make_doc([], machine=found)) == []


def test_collect_detects_containers_vms_and_mixed_governors(sysroot: Path):
    _write(
        sysroot, "sys/devices/system/cpu/cpu1/cpufreq/scaling_governor", "performance"
    )
    _write(sysroot, "proc/1/cgroup", "0::/kubepods/besteffort/pod1\n")
    _write(sysroot, "proc/cpuinfo", CPUINFO.replace("msr", "msr hypervisor"))
    (sysroot / "sys/devices/system/cpu/intel_pstate/no_turbo").write_text("1")
    found = machine.collect(sysroot, system="Linux", python_version="3.12.8")
    assert found["governor"] == "mixed(performance,powersave)"
    assert found["container"] is True
    assert found["virtualized"] is True
    assert found["turbo"] is False


def test_collect_on_other_systems_marks_linux_facts_unknown(sysroot: Path):
    found = machine.collect(sysroot, system="Windows", python_version="3.12.8")
    assert found["governor"] is None
    assert found["turbo"] is None
    assert found["cgroup_v2"] is None
    assert found["container"] is None
    assert found["virtualized"] is None
    assert found["os"] == "Windows"


def test_boost_file_is_the_turbo_fallback(sysroot: Path):
    (sysroot / "sys/devices/system/cpu/intel_pstate/no_turbo").unlink()
    _write(sysroot, "sys/devices/system/cpu/cpufreq/boost", "1")
    assert machine.collect(sysroot, system="Linux")["turbo"] is True


@pytest.mark.parametrize(
    ("model", "short", "slug"),
    [
        ("AMD Ryzen 9 7950X 16-Core Processor", "AMD Ryzen 9 7950X", "ryzen-9-7950x"),
        ("Intel(R) Core(TM) i9-13900K", "Intel Core i9-13900K", "core-i9-13900k"),
        (
            "Intel(R) Xeon(R) Platinum 8375C CPU @ 2.90GHz",
            "Intel Xeon Platinum 8375C",
            "xeon-platinum-8375c",
        ),
        ("AMD EPYC 7763 64-Core Processor", "AMD EPYC 7763", "epyc-7763"),
        ("Apple M2 Pro", "Apple M2 Pro", "apple-m2-pro"),
        (None, "unknown CPU", "unknown-cpu"),
    ],
)
def test_cpu_names(model: str | None, short: str, slug: str):
    assert machine.short_cpu_model(model) == short
    assert machine.cpu_slug(model) == slug


def test_profile_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(machine.PROFILE_ENV, raising=False)
    assert (
        machine.profile_id(
            "Linux", "x86_64", "AMD Ryzen 9 7950X 16-Core Processor", "3.12.8"
        )
        == "linux-x86_64-ryzen-9-7950x-py3.12"
    )
    monkeypatch.setenv(machine.PROFILE_ENV, "graviton-arm64")
    assert machine.profile_id("Linux", "arm64", None, "3.12.8") == "graviton-arm64"
    monkeypatch.setenv(machine.PROFILE_ENV, "Bad/Profile Name")
    assert machine.profile_id("Linux", "arm64", None, "3.12.8") == "bad-profile-name"


def test_normalize_arch():
    assert machine.normalize_arch("AMD64") == "x86_64"
    assert machine.normalize_arch("aarch64") == "arm64"
    assert machine.normalize_arch("x86_64") == "x86_64"
    assert machine.normalize_arch("") == "unknown"


def _statuses(found: machine.MachineDoc) -> dict[str, str]:
    return {check.name: check.status for check in machine.checks(found)}


def test_checks_warn_about_noisy_settings():
    noisy = make_machine(
        governor="powersave",
        turbo=True,
        load_avg_1m=3.2,
        ac_power=False,
        virtualized=True,
    )
    statuses = _statuses(noisy)
    assert statuses["governor"] == "warn"
    assert statuses["turbo"] == "warn"
    assert statuses["load"] == "warn"
    assert statuses["power"] == "warn"
    assert statuses["virtualized"] == "warn"
    assert machine.warning_count(noisy) == 5
    hints = {check.name: check.hint for check in machine.checks(noisy)}
    assert hints["governor"] == (
        "run `sudo cpupower frequency-set -g performance` for stable numbers"
    )


def test_checks_pass_on_a_quiet_machine():
    quiet = make_machine(
        governor="performance", turbo=False, load_avg_1m=0.1, ac_power=True
    )
    assert machine.warning_count(quiet) == 0
    statuses = _statuses(quiet)
    assert statuses["governor"] == "ok"
    assert statuses["chromium"] == "info"


def test_unknown_facts_are_informational():
    unknown = make_machine(
        governor=None,
        turbo=None,
        load_avg_1m=None,
        virtualized=None,
        cgroup_v2=None,
        container=None,
    )
    assert machine.warning_count(unknown) == 0
    values = {check.name: check.value for check in machine.checks(unknown)}
    assert values["governor"] == "unknown (no cpufreq)"
    assert values["load"] == "unknown"
