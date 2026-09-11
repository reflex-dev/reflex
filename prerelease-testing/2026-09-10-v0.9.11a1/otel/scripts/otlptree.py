"""Print a span tree from OTLP export JSON lines (protobuf-MessageToDict or JSON)."""
import base64, json, sys, glob
from collections import defaultdict

def hexify(v):
    if isinstance(v, str):
        try:
            b = base64.b64decode(v + "=" * (-len(v) % 4), validate=False)
            if len(b) in (8, 16):
                return b.hex()
        except Exception:
            pass
        return v
    return v

spans = []
for pat in sys.argv[1:]:
    for f in glob.glob(pat):
        for line in open(f):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            for rs in d.get("resource_spans", d.get("resourceSpans", [])):
                res = {}
                for a in rs.get("resource", {}).get("attributes", []):
                    res[a["key"]] = list(a["value"].values())[0]
                for ss in rs.get("scope_spans", rs.get("scopeSpans", [])):
                    scope = ss.get("scope", {}).get("name")
                    for s in ss.get("spans", []):
                        attrs = {}
                        for a in s.get("attributes", []):
                            v = a["value"]
                            attrs[a["key"]] = list(v.values())[0] if v else None
                        spans.append({
                            "name": s["name"],
                            "kind": s.get("kind"),
                            "trace": hexify(s.get("trace_id") or s.get("traceId")),
                            "span": hexify(s.get("span_id") or s.get("spanId")),
                            "parent": hexify(s.get("parent_span_id") or s.get("parentSpanId") or ""),
                            "attrs": attrs,
                            "svc": res.get("service.name"),
                            "scope": scope,
                            "start": s.get("start_time_unix_nano") or s.get("startTimeUnixNano"),
                            "events": [e["name"] for e in s.get("events", [])],
                            "status": s.get("status", {}),
                        })
spans.sort(key=lambda s: int(s["start"] or 0))
by = {s["span"]: s for s in spans}
kids = defaultdict(list)
roots = []
for s in spans:
    if s["parent"] and s["parent"] in by:
        kids[s["parent"]].append(s)
    else:
        roots.append(s)

def show(s, i=0):
    extra = ""
    if s["events"]:
        extra += " EVENTS=" + ",".join(s["events"])
    if s["status"].get("code"):
        extra += f" STATUS={s['status']}"
    print("  " * i + f"- {s['name']} [{s['kind']}] svc={s['svc']} scope={s['scope']} "
          f"trace={s['trace'][-8:]} span={s['span'][-6:]} parent={(s['parent'] or 'ROOT')[-6:]}{extra}")
    if s["attrs"]:
        print("  " * (i + 1) + "attrs " + json.dumps(s["attrs"]))
    for c in kids[s["span"]]:
        show(c, i + 1)

for r in roots:
    show(r)
print(f"\nTOTAL {len(spans)} spans, {len(roots)} roots")
