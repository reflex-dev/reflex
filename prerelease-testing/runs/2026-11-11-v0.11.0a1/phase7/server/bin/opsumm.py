"""Summarize oplock.sh jsonl: per (tag, conc) runs stalled (api_max > 500 ms), worst api_max, correctness."""
import collections, json, sys
cells = collections.defaultdict(list)
for line in open(sys.argv[1]):
    d = json.loads(line)
    if "|conc" not in d["label"]:
        print(d); continue
    tag, conc, _ = d["label"].split("|"); cells[(tag, conc)].append(d)
for (tag, conc), rs in cells.items():
    st = sum((r["api_max"] or 0) > 500 for r in rs)
    print(f"{tag:<16} {conc:<6} stalled {st}/{len(rs)}  api_max(ms) {[round(r['api_max'] or 0) for r in rs]}  api_p99 max {max(r['api_p99'] or 0 for r in rs):.0f}  exact {sum(r['ok']==r['of'] for r in rs)}/{len(rs)}  api_pids {sorted({p for r in rs for p in r['api_pids']})[:6]}")
