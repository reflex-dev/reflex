"""Pretty-print a span dump as a forest."""
import json, sys, glob
from collections import defaultdict

files = []
for a in sys.argv[1:]:
    files.extend(glob.glob(a))
spans = []
for f in files:
    for line in open(f):
        line = line.strip()
        if line:
            d = json.loads(line)
            d["_file"] = f.rsplit("/", 1)[-1]
            spans.append(d)
spans.sort(key=lambda d: d["start_time"])
by_id = {s["context"]["span_id"]: s for s in spans}
children = defaultdict(list)
roots = []
for s in spans:
    p = s.get("parent_id")
    if p and p in by_id:
        children[p].append(s)
    else:
        roots.append(s)

def show(s, ind=0):
    a = s.get("attributes") or {}
    ev = s.get("events") or []
    st = s.get("status") or {}
    extra = ""
    if ev:
        extra += " EVENTS=" + ",".join(e["name"] for e in ev)
    if st.get("status_code") not in (None, "UNSET"):
        extra += f" STATUS={st.get('status_code')}:{st.get('description','')[:60]}"
    print("  " * ind + f"- {s['name']} [{s['kind'].replace('SpanKind.','')}] "
          f"trace={s['context']['trace_id'][-8:]} span={s['context']['span_id'][-6:]} "
          f"parent={(s.get('parent_id') or 'ROOT')[-6:]} pid={s['_file']}{extra}")
    if a:
        print("  " * (ind + 1) + "attrs " + json.dumps(a))
    for c in sorted(children[s["context"]["span_id"]], key=lambda x: x["start_time"]):
        show(c, ind + 1)

for r in roots:
    show(r)
print(f"\nTOTAL {len(spans)} spans, {len(roots)} roots")
