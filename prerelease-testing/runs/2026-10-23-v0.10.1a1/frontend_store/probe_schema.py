"""#7553: is the frontend state-schema hash stable where it must be, and sensitive where it must be?

Runs schema_app's module in child processes (fresh interpreter each, different PYTHONHASHSEED and
env flags) and prints the hash per configuration. Also evaluates pages in two orders to see whether
ComponentState instance names (and so the hash) depend on evaluation order.

    EXPECT_VENV=new $SB/envs/new/bin/python probe_schema.py
"""

import json
import os
import subprocess
import sys
import textwrap

APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema_app")
CHILD = textwrap.dedent(
    """
    import os, sys, json
    sys.path.insert(0, %r)
    os.chdir(%r)
    import reflex as rx
    assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__
    import schema_app.schema_app as m
    order = os.environ.get("PAGE_ORDER", "")
    pages = {"index": m.index, "second": m.second, "item": m.item}
    names = []
    for name in (order.split(",") if order else []):
        pages[name]()
        names.append(name)
    out = {"hash": rx.State._to_frontend_schema(), "evaluated": names,
           "states": sorted(s.get_full_name().split(".")[-1] for s in rx.State.get_substates()) if hasattr(rx.State, "get_substates") else None}
    print("RESULT " + json.dumps(out))
    """
) % (APP_DIR, APP_DIR)


def run(env_extra: dict, label: str) -> str:
    env = {**os.environ, **env_extra, "REFLEX_TELEMETRY_ENABLED": "false"}
    r = subprocess.run([sys.executable, "-c", CHILD], env=env, capture_output=True, text=True, timeout=120)
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("RESULT ")), None)
    if line is None:
        print(f"{label:48s} FAILED: {r.stderr.strip().splitlines()[-1:] }")
        return ""
    data = json.loads(line[7:])
    print(f"{label:48s} {data['hash']}  evaluated={data['evaluated']}")
    return data["hash"]


base = run({"PYTHONHASHSEED": "1"}, "base (seed 1, no pages evaluated)")
run({"PYTHONHASHSEED": "2"}, "base (seed 2)")
run({"PYTHONHASHSEED": "random"}, "base (seed random)")
a = run({"PYTHONHASHSEED": "3", "PAGE_ORDER": "index,second,item"}, "pages index,second,item")
b = run({"PYTHONHASHSEED": "4", "PAGE_ORDER": "second,index,item"}, "pages second,index,item")
c = run({"PYTHONHASHSEED": "5", "PAGE_ORDER": "index"}, "pages index only")
d = run({"PYTHONHASHSEED": "5", "PAGE_ORDER": "index,index"}, "page index evaluated twice")
run({"PYTHONHASHSEED": "6", "SCHEMA_DEFAULT": "1"}, "default-only change (must equal base)")
run({"PYTHONHASHSEED": "7", "SCHEMA_RENAME": "1"}, "handler renamed (must differ)")
run({"PYTHONHASHSEED": "8", "SCHEMA_EXTRA": "1"}, "extra substate+var (must differ)")
print()
print("stable across seeds:", base == run({"PYTHONHASHSEED": "9"}, "base (seed 9)"))
print("page evaluation order changes hash:", a != b, "| evaluating a subset changes hash:", a != c, "| double evaluation changes hash:", c != d)
