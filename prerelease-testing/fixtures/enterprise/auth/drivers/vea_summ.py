"""Summarize A3-09 runs: per rep, where the tab ends after the return/boot, who, flash of protected value, protected click outcome."""
import json
import sys

import playwright  # noqa: F401

assert ("/envs/" + __import__("os").environ.get("DRV_VENV", "driver") + "/") in playwright.__file__, playwright.__file__

for path in sys.argv[1:]:
    for r in json.load(open(path)):
        seq = next((row["seq"] for row in r.get("rows", []) if row.get("step") == "P_boot_seq"), [])
        cseq = r.get("click_seq") or []
        print(
            f"{r['label']:22s} {r['scenario']:5s} rep{r['rep']} login={r.get('login')} after_boot={r.get('after_boot')} "
            f"flash={r.get('flash')} boot_seq={[s[:3] for s in seq][:5]} click_end={cseq[-1][:3] if cseq else None} "
            f"{('ERR ' + r['error'][:80]) if 'error' in r else ''}"
        )
