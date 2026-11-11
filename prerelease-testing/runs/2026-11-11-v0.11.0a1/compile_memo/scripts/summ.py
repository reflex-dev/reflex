import json, sys
d = json.load(open(sys.argv[1]))
for k, v in d.items():
    if k == "console":
        seen = {}
        for c in v:
            key = (c["page"], c["type"], c["text"][:160])
            seen[key] = seen.get(key, 0) + 1
        print("CONSOLE:")
        for (p, t, x), n in seen.items():
            print(f"  [{p}] {t} x{n}: {x!r}")
        continue
    if isinstance(v, dict):
        v = dict(v)
        if "js_requests" in v:
            v["js_requests"] = f"{len(v['js_requests'])} files; " + ",".join(x for x in v["js_requests"] if any(s in x for s in ("plotly", "recharts", "glide", "data-editor", "lucide", "dataeditor")))
    print(k, "=", json.dumps(v, indent=None)[:3000])
