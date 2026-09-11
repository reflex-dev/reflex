"""Which of --json / --interactive / --loglevel does each `reflex cloud` leaf accept?"""
import json, os, re, subprocess, sys

REFLEX = sys.argv[1]
OUT = sys.argv[2]
ENV = dict(os.environ, REFLEX_TELEMETRY_ENABLED="false", NO_COLOR="1", COLUMNS="200")
ENV.pop("REFLEX_CLOUD_TOKEN", None)

def run(args, timeout=60):
    p = subprocess.run([REFLEX, *args], capture_output=True, text=True, timeout=timeout, env=ENV, cwd="/tmp")
    return p.returncode, p.stdout, p.stderr

def subcommands(path):
    rc, out, err = run([*path, "--help"]); text = out + err
    cmds, in_cmds = [], False
    for line in text.splitlines():
        if re.match(r"^\s*(Commands|╭─+ Commands)", line): in_cmds = True; continue
        if in_cmds:
            m = re.match(r"^\s*[│|]?\s*([a-z][a-z0-9-]*)\s{2,}", line)
            if m: cmds.append(m.group(1))
            elif re.match(r"^\s*╰", line): in_cmds = False
    return cmds

leaves = []
for c1 in subcommands(["cloud"]):
    subs = subcommands(["cloud", c1])
    if subs:
        for c2 in subs:
            s2 = subcommands(["cloud", c1, c2])
            leaves += [["cloud", c1, c2, c3] for c3 in s2] if s2 else [["cloud", c1, c2]]
    else:
        leaves.append(["cloud", c1])
leaves.append(["deploy"])

rows = {}
for leaf in leaves:
    rc, out, err = run([*leaf, "--help"])
    h = out + err
    rows[" ".join(leaf)] = {
        "json": "--json" in h,
        "no_json": "--no-json" in h,
        "interactive": "--interactive" in h,
        "no_interactive": "--no-interactive" in h,
        "loglevel": "--loglevel" in h,
        "token": "--token" in h,
        "follow": "--follow" in h,
        "help_text": h,
    }
json.dump(rows, open(OUT, "w"), indent=1)
hdr = ["command", "json", "no-json", "-i", "--no-interactive", "loglevel", "token", "follow"]
w = max(len(k) for k in rows) + 1
print(f"{'command'.ljust(w)} json  nojson  -i   noint  loglvl token follow")
for k, v in rows.items():
    print(f"{k.ljust(w)} {str(v['json'])[0]:5} {str(v['no_json'])[0]:7} {str(v['interactive'])[0]:4} {str(v['no_interactive'])[0]:6} {str(v['loglevel'])[0]:6} {str(v['token'])[0]:5} {str(v['follow'])[0]}")
