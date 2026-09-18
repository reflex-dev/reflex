"""Guards on the CI gate convention in .github/workflows and .github/rulesets.

Branch rules match a status check by name, literally. A workflow that a path
filter skips never reports its checks, and a matrix job's name changes with the
matrix, so neither can be named in a rule directly. Every merge-blocking
workflow therefore ends in a gate job with a fixed name, and these tests keep the
workflows, the gates and the ruleset from drifting apart.
"""

import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
RULESET = REPO_ROOT / ".github" / "rulesets" / "main-required-checks.json"
GATE_SUFFIX = "-gate"
ACTIONS_APP_ID = 15368
# Workflows with a single job whose check name cannot drift are required by that
# name instead of through a gate.
DIRECTLY_REQUIRED = {"pre-commit", "dependency-review", "changelog"}


def workflow_triggers(doc: dict) -> dict:
    """Return a workflow's `on:` block as a dict, however YAML parsed it."""
    raw = doc.get(True, doc.get("on"))
    if isinstance(raw, str):
        return {raw: None}
    if isinstance(raw, list):
        return dict.fromkeys(raw)
    return raw or {}


WORKFLOWS = {
    path.name: yaml.safe_load(path.read_text())
    for path in sorted(WORKFLOW_DIR.glob("*.yml"))
}
PR_WORKFLOWS = [
    name for name, doc in WORKFLOWS.items() if "pull_request" in workflow_triggers(doc)
]
GATED_WORKFLOWS = [
    name
    for name, doc in WORKFLOWS.items()
    if any(job.endswith(GATE_SUFFIX) for job in doc.get("jobs", {}))
]


def gate_id(name: str) -> str:
    """Return the gate job's id for a workflow known to have one."""
    return next(
        job for job in WORKFLOWS[name].get("jobs", {}) if job.endswith(GATE_SUFFIX)
    )


def required_checks() -> list[dict]:
    """Return the required status checks the ruleset declares."""
    ruleset = json.loads(RULESET.read_text())
    rule = next(
        rule for rule in ruleset["rules"] if rule["type"] == "required_status_checks"
    )
    return rule["parameters"]["required_status_checks"]


@pytest.mark.parametrize("name", PR_WORKFLOWS)
def test_pull_request_trigger_carries_no_path_filter(name):
    trigger = workflow_triggers(WORKFLOWS[name])["pull_request"] or {}
    filters = {"paths", "paths-ignore"} & set(trigger)
    assert not filters, (
        f"{name} filters its pull_request trigger on {sorted(filters)}. A workflow "
        "a path filter skips never reports its checks, so a required check on it "
        "blocks every merge. Filter in a `changes` job instead."
    )


@pytest.mark.parametrize("name", PR_WORKFLOWS)
def test_pull_request_workflow_contributes_a_required_check(name):
    jobs = set(WORKFLOWS[name].get("jobs", {}))
    gates = {job for job in jobs if job.endswith(GATE_SUFFIX)}
    assert gates or jobs <= DIRECTLY_REQUIRED, (
        f"{name} runs on pull requests but contributes no required check: add a "
        f"'{GATE_SUFFIX}' job, or require its jobs by name."
    )


@pytest.mark.parametrize("name", GATED_WORKFLOWS)
def test_gate_job_needs_every_other_job(name):
    jobs = WORKFLOWS[name]["jobs"]
    gate = gate_id(name)
    needs = jobs[gate].get("needs", [])
    needs = [needs] if isinstance(needs, str) else needs
    assert set(needs) == set(jobs) - {gate}, (
        f"{name}: {gate} must list every other job in `needs`, otherwise a failure "
        "in the job it omits never reaches the required check."
    )


@pytest.mark.parametrize("name", GATED_WORKFLOWS)
def test_gate_job_always_runs(name):
    condition = str(WORKFLOWS[name]["jobs"][gate_id(name)].get("if", ""))
    assert condition == "always()", (
        f"{name}: the gate needs `if: always()`. Under `!cancelled()` a cancelled "
        "run reports the gate as skipped, which counts as a pass."
    )


def test_ruleset_requires_exactly_the_gates():
    contexts = {check["context"] for check in required_checks()}
    gates = {gate_id(name) for name in GATED_WORKFLOWS}
    assert contexts == gates | DIRECTLY_REQUIRED, (
        "the ruleset and the workflows disagree about what blocks a merge; "
        f"only in the ruleset: {sorted(contexts - gates - DIRECTLY_REQUIRED)}, "
        f"only in the workflows: {sorted((gates | DIRECTLY_REQUIRED) - contexts)}"
    )


def test_ruleset_pins_every_check_to_the_actions_app():
    unpinned = [
        check["context"]
        for check in required_checks()
        if check.get("integration_id") != ACTIONS_APP_ID
    ]
    assert not unpinned, (
        f"{unpinned} are not pinned to the GitHub Actions app, so another "
        "integration could satisfy them by posting a same-named check."
    )
