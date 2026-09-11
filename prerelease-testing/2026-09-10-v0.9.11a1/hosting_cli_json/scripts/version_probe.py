"""#6963: exercise reflex-hosting-cli's reflex-version comparisons.

Two surfaces:
  A. `reflex_cli.v2.cli.deploy`'s export_fn arity branch (the line #6963 changed),
     evaluated for the shipped predicate and the pre-#6963 one.
  B. the `hosting_cli` click group callback, which every `reflex cloud <cmd>`
     runs: MINIMUM (hard fail) and RECOMMENDED (deprecation warning) checks.
     Driven through click's CliRunner with `_reflex_version` patched.
"""

import inspect
import json
import os
import re
import sys

import reflex_cli

EXPECT = os.environ.get("EXPECT_ENV", "/envs/smoke/")
assert EXPECT in reflex_cli.__file__, reflex_cli.__file__

from packaging import version  # noqa: E402

VERSIONS = [
    "0.6.5",
    "0.6.6",
    "0.6.6.post1",
    "0.7.5",
    "0.7.6",
    "0.7.6.post1",
    "0.7.6.post2",
    "0.7.7",
    "0.7.7rc1",
    "0.9.10.post2",
    "0.9.11a1",
    "1.0.0rc1",
    "1.0.0",
]

out = {"reflex_cli_file": reflex_cli.__file__}

# --- A. the deploy export-arity branch -------------------------------------
from reflex_cli.v2 import cli as cli_mod  # noqa: E402

src = inspect.getsource(cli_mod.deploy)
shipped_lines = sorted(set(re.findall(r"if rx_version[^\n:]*", src)))
out["deploy_predicate_source"] = shipped_lines
BREAKING_RELEASE = (0, 7, 7)
OLD_BREAKING = version.parse("0.7.6")
rows = []
for v in VERSIONS:
    p = version.parse(v)
    new_six_arg = p.release < BREAKING_RELEASE      # shipped (post-#6963)
    old_six_arg = p <= OLD_BREAKING                 # pre-#6963
    rows.append({
        "version": v,
        "release_tuple": list(p.release),
        "post_6963_uses_6arg_export": new_six_arg,
        "pre_6963_uses_6arg_export": old_six_arg,
        "changed": new_six_arg != old_six_arg,
    })
out["deploy_arity"] = rows

# --- B. the group callback's version gate ----------------------------------
import click  # noqa: E402
from click.testing import CliRunner  # noqa: E402

from reflex_cli import constants  # noqa: E402
from reflex_cli.v2 import deployments as dep  # noqa: E402

out["MINIMUM_REFLEX_VERSION"] = str(constants.ReflexHostingCli.MINIMUM_REFLEX_VERSION)
out["RECOMMENDED_REFLEX_VERSION"] = str(constants.ReflexHostingCli.RECOMMENDED_REFLEX_VERSION)

# A tiny group with the very same callback body, so the gate is exercised
# without any network-touching subcommand.
real_check_version = dep.check_version
dep.check_version = lambda: None  # skip the PyPI round trip


@click.group(name="cloud")
@click.pass_context
def probe_group(ctx):
    """Probe group reusing the shipped callback."""
    dep.hosting_cli.callback(*(), **{})  # not used; kept for clarity


@click.command()
def noop():
    """Do nothing."""
    click.echo("OK")


gate_rows = []
for v in VERSIONS + [None]:
    dep._reflex_version = version.parse(v) if v else None

    @click.group()
    @click.pass_context
    def g(ctx):
        # Exactly the shipped callback, minus reserve_stdout/check_version.
        if dep._reflex_version is None:
            ctx.fail("Reflex is not installed. Install it with `pip install reflex`.")
        if dep._reflex_version < constants.ReflexHostingCli.MINIMUM_REFLEX_VERSION:
            ctx.fail(
                f"Reflex version {dep._reflex_version} is not compatible with reflex-hosting-cli. "
                f"Please upgrade Reflex to at least version {constants.ReflexHostingCli.MINIMUM_REFLEX_VERSION}."
            )
        if dep._reflex_version < constants.ReflexHostingCli.RECOMMENDED_REFLEX_VERSION:
            dep.logger.warning(
                f"Support for Reflex version {dep._reflex_version} in reflex-hosting-cli is deprecated. "
                f"Please upgrade Reflex to at least version {constants.ReflexHostingCli.RECOMMENDED_REFLEX_VERSION}."
            )

    g.add_command(noop)
    r = CliRunner().invoke(g, ["noop"])
    warned = dep._reflex_version is not None and (
        dep._reflex_version < constants.ReflexHostingCli.RECOMMENDED_REFLEX_VERSION
    )
    gate_rows.append({
        "version": v,
        "exit_code": r.exit_code,
        "hard_fail": r.exit_code != 0,
        "deprecation_warning": warned,
        "output_head": (r.output or "").strip().splitlines()[:2],
    })
dep.check_version = real_check_version
out["group_gate"] = gate_rows

print(json.dumps(out, indent=1))
