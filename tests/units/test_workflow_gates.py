"""Guards on the CI gate convention in .github/workflows and .github/rulesets.

Branch rules match a status check by name, literally. A workflow that a path
filter skips never reports its checks, and a matrix job's name changes with the
matrix, so neither can be named in a rule directly. Every merge-blocking
workflow therefore ends in a gate job with a fixed name, and these tests keep the
workflows, the gates and the ruleset from drifting apart.

The filter ban follows from that and no further: a workflow nothing requires may
filter its trigger freely, because the filter then costs it a run rather than a
merge.
"""

import json
from pathlib import Path

import pytest
import yaml

from scripts import changed_paths

REPO_ROOT = Path(__file__).parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
ACTION_DIR = REPO_ROOT / ".github" / "actions"
RULESET = REPO_ROOT / ".github" / "rulesets" / "main-required-checks.json"
GATE_SUFFIX = "-gate"
ACTIONS_APP_ID = 15368
# Workflows with a single job whose check name cannot drift are required by that
# name instead of through a gate.
DIRECTLY_REQUIRED = {"pre-commit", "changelog"}
# Required checks that apps other than GitHub Actions post, carried over from the
# branch protection this ruleset replaces. No gate can cover another app's check,
# so each is required by name and pinned to the app that posts it.
THIRD_PARTY = {"Greptile Review": 867647, "cubic · AI code reviewer": 1082092}
# Workflows that deliberately block no merge, so they stay out of the ruleset.
# Three keep the trigger-level path filter that would deadlock a required check
# (docs_whitelist, and the reflex-bench playground's examples and size_budgets);
# the other two are disabled in the repository's Actions settings, where they
# never run at all -- which no test here can see, so disabling a workflow means
# moving it here by hand.
ADVISORY = {
    "docs_whitelist.yml",
    "check_node_latest.yml",
    "dependency-review.yml",
    "examples.yml",
    "size_budgets.yml",
}


def workflow_triggers(doc: dict) -> dict:
    """Return a workflow's `on:` block as a dict, however YAML parsed it."""
    raw = doc.get(True, doc.get("on"))
    if isinstance(raw, str):
        return {raw: None}
    if isinstance(raw, list):
        return dict.fromkeys(raw)
    return raw or {}


WORKFLOWS = {
    path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
    for path in sorted(WORKFLOW_DIR.glob("*.yml"))
}
PR_WORKFLOWS = [
    name for name, doc in WORKFLOWS.items() if "pull_request" in workflow_triggers(doc)
]
REQUIRED_PR_WORKFLOWS = [name for name in PR_WORKFLOWS if name not in ADVISORY]
GATED_WORKFLOWS = [
    name
    for name, doc in WORKFLOWS.items()
    if any(job.endswith(GATE_SUFFIX) for job in doc.get("jobs", {}))
]
CHANGES_STEPS = [
    (name, step)
    for name, doc in WORKFLOWS.items()
    for job in doc.get("jobs", {}).values()
    for step in job.get("steps", [])
    if step.get("uses") == "./.github/actions/changed_paths"
]


def gate_id(name: str) -> str:
    """Return the gate job's id for a workflow known to have one."""
    return next(
        job for job in WORKFLOWS[name].get("jobs", {}) if job.endswith(GATE_SUFFIX)
    )


def required_checks() -> list[dict]:
    """Return the required status checks the ruleset declares."""
    ruleset = json.loads(RULESET.read_text(encoding="utf-8"))
    rule = next(
        rule for rule in ruleset["rules"] if rule["type"] == "required_status_checks"
    )
    return rule["parameters"]["required_status_checks"]


@pytest.mark.parametrize("name", REQUIRED_PR_WORKFLOWS)
def test_required_workflow_has_no_pull_request_path_filter(name):
    trigger = workflow_triggers(WORKFLOWS[name])["pull_request"] or {}
    filters = {"paths", "paths-ignore"} & set(trigger)
    assert not filters, (
        f"{name} filters its pull_request trigger on {sorted(filters)}. A workflow "
        "a path filter skips never reports its checks, so a required check on it "
        f"blocks every merge. Filter in a `changes` job instead, or add {name} to "
        "ADVISORY and drop it from the ruleset."
    )


@pytest.mark.parametrize("name", REQUIRED_PR_WORKFLOWS)
def test_pull_request_workflow_contributes_a_required_check(name):
    jobs = set(WORKFLOWS[name].get("jobs", {}))
    gates = {job for job in jobs if job.endswith(GATE_SUFFIX)}
    assert gates or jobs <= DIRECTLY_REQUIRED, (
        f"{name} runs on pull requests but contributes no required check: add a "
        f"'{GATE_SUFFIX}' job, require its jobs by name, or mark it ADVISORY."
    )


@pytest.mark.parametrize("name", sorted(ADVISORY))
def test_advisory_workflow_is_absent_from_the_ruleset(name):
    assert name in WORKFLOWS, f"{name} is marked ADVISORY but no longer exists"
    required = {check["context"] for check in required_checks()}
    listed = set(WORKFLOWS[name].get("jobs", {})) & required
    assert not listed, (
        f"{name} is marked ADVISORY, so it keeps a trigger path filter and cannot "
        f"report on every pull request, yet the ruleset requires {sorted(listed)}."
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


def test_directly_required_checks_are_posted():
    posted = {
        job.get("name", job_id)
        for name in REQUIRED_PR_WORKFLOWS
        for job_id, job in WORKFLOWS[name].get("jobs", {}).items()
    }
    missing = DIRECTLY_REQUIRED - posted
    assert not missing, (
        f"the ruleset requires {sorted(missing)} by name, but no workflow that runs "
        "on pull requests has a job posting that check, so every merge would wait "
        "on it forever."
    )


@pytest.mark.parametrize("name", GATED_WORKFLOWS)
def test_gate_job_runs_the_ci_gate_action(name):
    steps = WORKFLOWS[name]["jobs"][gate_id(name)].get("steps", [])
    gate_steps = [
        step for step in steps if step.get("uses") == "./.github/actions/ci_gate"
    ]
    # Any other step reports the required check green whatever the jobs it needs did.
    assert gate_steps, f"{name}: the gate never runs ./.github/actions/ci_gate"
    expected = "${{ toJSON(needs) }}"
    given = [step.get("with", {}).get("needs") for step in gate_steps]
    assert set(given) == {expected}, (
        f"{name}: the gate must hand ci_gate {expected}, not {given}"
    )
    # A condition can skip the step and continue-on-error can swallow its failure;
    # either way the job, and with it the required check, still passes.
    lenient = [
        key for step in gate_steps for key in ("if", "continue-on-error") if key in step
    ]
    assert not lenient, f"{name}: the ci_gate step must not set {lenient}"


@pytest.mark.parametrize(
    ("name", "step"), CHANGES_STEPS, ids=[name for name, _ in CHANGES_STEPS]
)
def test_changes_filter_compiles(name, step):
    inputs = step.get("with", {})
    given = [key for key in ("paths", "paths-ignore") if inputs.get(key, "").strip()]
    assert len(given) == 1, (
        f"{name}: the changes step takes exactly one of paths or paths-ignore, "
        f"got {given}"
    )
    # A pattern the evaluator rejects fails the `changes` job at run time, and with
    # it the gate on every pull request; catch it here instead.
    changed_paths.compile_filters(changed_paths.lines(inputs[given[0]]))


@pytest.mark.parametrize("name", GATED_WORKFLOWS)
def test_gated_jobs_do_not_continue_on_error(name):
    lenient = [
        job_id
        for job_id, job in WORKFLOWS[name]["jobs"].items()
        if job.get("continue-on-error")
    ]
    assert not lenient, (
        f"{name}: {lenient} set continue-on-error, and a job that fails under it "
        "reports success in the gate's `needs`, so the gate passes over it."
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
    expected = (
        {gate_id(name) for name in GATED_WORKFLOWS}
        | DIRECTLY_REQUIRED
        | set(THIRD_PARTY)
    )
    assert contexts == expected, (
        "the ruleset and the workflows disagree about what blocks a merge; "
        f"only in the ruleset: {sorted(contexts - expected)}, "
        f"only in the workflows: {sorted(expected - contexts)}"
    )


def test_ruleset_pins_every_check_to_its_app():
    misattributed = [
        check["context"]
        for check in required_checks()
        if check.get("integration_id")
        != THIRD_PARTY.get(check["context"], ACTIONS_APP_ID)
    ]
    assert not misattributed, (
        f"{misattributed} are not pinned to the app that posts them, so another "
        "integration could satisfy them by posting a same-named check."
    )


@pytest.mark.parametrize(
    "path", sorted(ACTION_DIR.glob("*/action.yml")), ids=lambda path: path.parent.name
)
def test_action_descriptions_carry_no_expressions(path):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    descriptions = [doc.get("description", "")] + [
        field.get("description", "")
        for section in ("inputs", "outputs")
        for field in (doc.get(section) or {}).values()
    ]
    offending = [text for text in descriptions if "${{" in text]
    assert not offending, (
        f"{path.parent.name}: the runner evaluates expressions even in action "
        "descriptions, and one naming a context the manifest cannot see, such "
        f"as `needs`, stops the action from loading at all: {offending}"
    )
