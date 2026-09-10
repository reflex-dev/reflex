"""Enumerate `reflex cloud` commands and check --json purity / exit codes off a TTY."""
import json, os, subprocess, sys, re

REFLEX = sys.argv[1]
ENV = dict(os.environ, REFLEX_TELEMETRY_ENABLED="false", NO_COLOR="1", COLUMNS="200")
ENV.pop("REFLEX_CLOUD_TOKEN", None)

def run(args, timeout=60):
    try:
        p = subprocess.run([REFLEX, *args], capture_output=True, text=True, timeout=timeout, env=ENV, cwd="/tmp")
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        return "TIMEOUT", (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), ""

def subcommands(path):
    rc, out, err = run([*path, "--help"])
    text = out + err
    cmds, in_cmds = [], False
    for line in text.splitlines():
        if re.match(r"^\s*(Commands|╭─+ Commands)", line):
            in_cmds = True; continue
        if in_cmds:
            m = re.match(r"^\s*[│|]?\s*([a-z][a-z0-9-]*)\s{2,}", line)
            if m: cmds.append(m.group(1))
            elif re.match(r"^\s*╰", line): in_cmds = False
    return cmds

leaves = []
for c1 in subcommands(["cloud"]):
    subs = subcommands(["cloud", c1])
    if subs:
        leaves += [["cloud", c1, c2] for c2 in subs]
    else:
        leaves.append(["cloud", c1])

report = {"leaf_count": len(leaves), "leaves": [" ".join(l) for l in leaves], "checks": {}}
for leaf in leaves:
    name = " ".join(leaf)
    entry = {}
    for label, extra in (("plain", []), ("json", ["--json"]), ("json_debug", ["--json", "--loglevel", "debug"])):
        rc, out, err = run([*leaf, *extra], timeout=45)
        stdout_lines = [l for l in out.splitlines() if l.strip()]
        parsed, parse_err = None, None
        if extra and stdout_lines:
            try:
                parsed = json.loads(out)
            except Exception as e:
                parse_err = f"{type(e).__name__}: {e}"[:120]
        entry[label] = {
            "rc": rc,
            "stdout_lines": len(stdout_lines),
            "stdout_head": stdout_lines[0][:120] if stdout_lines else "",
            "one_json_doc": parsed is not None,
            "json_parse_error": parse_err,
            "stderr_head": (err.strip().splitlines() or [""])[0][:140],
            "stderr_lines": len([l for l in err.splitlines() if l.strip()]),
        }
    report["checks"][name] = entry

print(json.dumps(report, indent=1))
