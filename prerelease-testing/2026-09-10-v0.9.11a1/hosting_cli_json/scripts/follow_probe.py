"""Drive the real `reflex cloud apps logs` command object with the network stubbed.

Offline, `apps logs` dies at authentication, so the `--follow` semantics are
unreachable from a shell. Here the two hosting helpers it calls are replaced and
the shipped click command is invoked through CliRunner, so the follow / json /
interactive interaction is exercised for real.
"""

import json
import os
import sys

import reflex_cli

EXPECT = os.environ.get("EXPECT_ENV", "/envs/smoke/")
assert EXPECT in reflex_cli.__file__, reflex_cli.__file__

from click.testing import CliRunner  # noqa: E402

from reflex_cli.utils import hosting  # noqa: E402
from reflex_cli.v2 import apps as apps_mod  # noqa: E402

PAGES = [
    (["line-A1", "line-A2"], "cursor-2"),
    (["line-B1"], None),
]
calls = {"n": 0}


def fake_client(token=None, interactive=True, **kw):
    return object()


def fake_get_app_logs(app_id, offset=None, start=None, end=None, client=None, cursor=None):
    i = calls["n"]
    calls["n"] += 1
    if i >= len(PAGES):
        return [[], None]
    rows, nxt = PAGES[i]
    return [list(rows), nxt] if nxt else list(rows)


hosting.get_authenticated_client = fake_client
hosting.get_app_logs = fake_get_app_logs
hosting.read_config = lambda *a, **k: None

CASES = [
    ("default", ["app1"], ""),
    ("follow_true_interactive", ["app1", "--follow", "true", "--interactive"], "exit\n"),
    ("follow_true_json", ["app1", "--follow", "true", "--json"], ""),
    ("follow_true_nointeractive", ["app1", "--follow", "true", "--no-interactive"], ""),
    ("follow_true_json_interactive", ["app1", "--follow", "true", "--json", "--interactive"], "exit\n"),
    ("follow_false_interactive", ["app1", "--follow", "false", "--interactive"], ""),
]

out = []
for name, args, stdin in CASES:
    calls["n"] = 0
    r = CliRunner().invoke(apps_mod.app_logs, args, input=stdin, catch_exceptions=True)
    out.append({
        "case": name,
        "args": args,
        "exit_code": r.exit_code,
        "pages_fetched": calls["n"],
        "output": r.output,
        "exception": repr(r.exception) if r.exception else None,
        "mentions_follow": "follow" in (r.output or "").lower(),
    })

print(json.dumps(out, indent=1))
