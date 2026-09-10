"""Print the four dev-server knob modes side by side from logs/knobs_<mode>/report.json.

    python summarize_knobs.py logs
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

MODES = ["plain", "prod_react", "warmup", "both"]


def main():
    logs = Path(sys.argv[1] if len(sys.argv) > 1 else "logs")
    reports = {}
    for m in MODES:
        p = logs / f"knobs_{m}" / "report.json"
        if p.exists():
            reports[m] = json.loads(p.read_text())
    modes = [m for m in MODES if m in reports]
    print("mode".ljust(34) + "".join(m.ljust(16) for m in modes))

    def row(label, fn):
        print(label.ljust(34) + "".join(str(fn(reports[m])).ljust(16) for m in modes))

    row("index cold load ms", lambda r: r["index_cold_ms"])
    for route in ["/page2", "/page3", "/about", "/long"]:
        row(f"first visit client nav {route} ms", lambda r, route=route: r["first_visit_client_nav_ms"].get(route))
    for route in ["/page2", "/page3", "/about", "/long"]:
        row(f"second visit client nav {route} ms", lambda r, route=route: r["second_visit_client_nav_ms"].get(route))
    for route in ["/page2", "/long"]:
        row(f"full load fresh ctx {route} ms", lambda r, route=route: r["full_load_fresh_context_ms"].get(route))
    row("count after 2 clicks", lambda r: r["count_after_2_clicks"])
    row("client_state after click", lambda r: r["cs_after_click"])
    row("toggle after click", lambda r: r["toggle_after_click"])
    row("fiber _debugOwner present", lambda r: r["fiber_debug_fields"]["has_debugOwner"])
    row("react.js dev markers", lambda r: sum(r["react_module_scan"].get("direct:react.js", {}).get("dev", {}).values()))
    row("react.js prod markers", lambda r: sum(r["react_module_scan"].get("direct:react.js", {}).get("prod", {}).values()))
    row("react-dom_client dev markers", lambda r: sum(r["react_module_scan"].get("direct:react-dom_client.js", {}).get("dev", {}).values()))
    row("react-dom_client prod markers", lambda r: sum(r["react_module_scan"].get("direct:react-dom_client.js", {}).get("prod", {}).values()))
    row("react-dom_client bytes", lambda r: r["react_module_scan"].get("direct:react-dom_client.js", {}).get("bytes"))
    row("edit -> vite frames", lambda r: ",".join(f.split(":")[0] for f in (r["edit"] or {}).get("vite_frames", [])))
    row("edit -> page reloads", lambda r: (r["edit"] or {}).get("page_loads_after_edit"))
    row("edit -> heading updated", lambda r: (r["edit"] or {}).get("heading_after"))
    row("edit -> client_state after", lambda r: (r["edit"] or {}).get("cs_after"))
    row("edit -> count after (backend)", lambda r: (r["edit"] or {}).get("count_after"))
    row("edit -> settle s", lambda r: (r["edit"] or {}).get("edit_to_settle_s"))
    row("page errors", lambda r: len(r["page_errors"]))
    row("console err/warn (non conn-refused)", lambda r: len([c for c in r["console_errors"] if "ERR_CONNECTION_REFUSED" not in c]))
    row("failed requests / 4xx-5xx", lambda r: f"{len(r['failed_requests'])}/{len(r['bad_responses'])}")
    for m in modes:
        extra = [c for c in reports[m]["console_errors"] if "ERR_CONNECTION_REFUSED" not in c]
        if extra:
            print(f"\n{m} console errors/warnings:")
            for c in extra:
                print("   ", c[:300])


if __name__ == "__main__":
    main()
