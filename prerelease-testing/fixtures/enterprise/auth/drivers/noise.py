"""Summarize console errors/warnings, page errors, failed requests and HTTP errors in a vdrv result."""
import collections
import json
import sys

res = json.load(open(sys.argv[1]))
c = collections.Counter()
for r in res:
    for key in [k for k in r if k.endswith("_log")]:
        for e in r[key]:
            k = e.get("kind")
            if k == "pageerror":
                c[("pageerror", e.get("text", "")[:120])] += 1
            elif k == "console" and e.get("type") in ("error", "warning"):
                c[("console." + e["type"], e.get("text", "")[:120])] += 1
            elif k == "requestfailed":
                c[("requestfailed", (e.get("url") or "")[:70] + " " + str(e.get("failure")))] += 1
            elif k == "http_error":
                c[("http_error", f"{e.get('status')} {(e.get('url') or '')[:80]}")] += 1
            elif k == "cookie_sync":
                c[("cookie_sync", str(e.get("status")))] += 1
for (k, t), n in c.most_common():
    print(f"{n:4d} {k:16s} {t}")
