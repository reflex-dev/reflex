"""Summarize metric names/attributes from a JSONL of MetricsData or OTLP exports."""
import json, sys, glob
seen = {}
for pat in sys.argv[1:]:
    for f in glob.glob(pat):
        for line in open(f):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            rms = d.get("resource_metrics") or d.get("resourceMetrics") or []
            for rm in rms:
                for sm in rm.get("scope_metrics", rm.get("scopeMetrics", [])):
                    scope = sm.get("scope", {}).get("name")
                    for m in sm.get("metrics", []):
                        data = m.get("data") or m.get("histogram") or m.get("sum") or {}
                        dps = data.get("data_points") or data.get("dataPoints") or []
                        for dp in dps:
                            a = dp.get("attributes")
                            if isinstance(a, list):
                                a = {x["key"]: list(x["value"].values())[0] for x in a}
                            key = (scope, m["name"], m.get("unit"), json.dumps(a, sort_keys=True))
                            seen[key] = seen.get(key, 0) + 1
for k in sorted(seen):
    print(f"{k[0]} | {k[1]} | unit={k[2]} | attrs={k[3]}")
print(f"\n{len(seen)} distinct (scope, metric, attribute-set) combinations")
