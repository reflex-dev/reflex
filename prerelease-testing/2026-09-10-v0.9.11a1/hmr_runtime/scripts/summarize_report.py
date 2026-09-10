"""Summarize one or more hmr_driver.py report.json files side by side.

    python summarize_report.py logs/hmr_new2/report.json logs/hmr_base/report.json
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path


def main():
    for path in sys.argv[1:]:
        r = json.loads(Path(path).read_text())
        print(f"\n##### {path} (label={r.get('label')})")
        il = r.get("initial_load", {})
        print("initial load ok:", il.get("ok"), "page_errors:", il.get("events", {}).get("page_errors"))
        for s in r["steps"]:
            e = s["events"]
            print(
                f"[{s['name']:11s}] {s.get('verdict', '?'):7s} settled={s['settled']} clicks={s['clicks_during_window']:2d} "
                f"count {s['count_before_edit']}->{s['count_actual_after_window']} ok={s['count_ok_after_window']} reset={s.get('state_reset_detected')} "
                f"post_click={s['post_update_click_ok']} focus={s['focus_after']['ok']} | sio attempts={e.get('socketio_attempts')} ok={e.get('socketio_successful_connections')} "
                f"first_ok=+{e.get('socketio_first_success_after_s')}s | vite first=+{e.get('vite_first_frame_after_s')}s frames={[f['type'] for f in e['vite_frames'] if f['type'] != 'custom']} "
                f"| state.js refetch={e['state_js_refetches']} ctx fetch={len(e['context_fetches'])} | page_errors={e['page_errors']} closed_before={e.get('ws_closed_before_established')} "
                f"addEvents_before={e.get('addEvents_before_provider')} | cs={s['after']['cs_text']!r} scratch={s['after'].get('scratch')!r} toggle={s['after']['toggle']!r} marks={s['after']['marks']}"
            )
            if e["console_errors"]:
                for c in e["console_errors"][:6]:
                    print("      console:", c[:220])
            if s.get("new_handler_click_ok") is not None:
                print("      new handler +10 click ok:", s["new_handler_click_ok"], s["new_handler_count"])
            if s.get("compiled_index_heading") is not None:
                print(f"      compiled heading={s['compiled_index_heading']!r} source heading={s['source_heading']!r}")
        c = collections.Counter()
        for m in r["all_events"]["console_all"]:
            k, t = m.split(":", 1)
            t = t.strip()
            c[(k, "ERR_CONNECTION_REFUSED ..." if "ERR_CONNECTION_REFUSED" in t else t[:120])] += 1
        print("console messages:")
        for (k, t), n in c.most_common():
            print(f"  {n:3d} {k}: {t}")
        print("nav after edits:", r.get("nav_after_edits"))
        ws = r.get("ws", [])
        print(
            "websockets: vite opens=", sum(1 for w in ws if w["kind"] == "vite"),
            "socket.io attempts=", sum(1 for w in ws if w["kind"] == "socketio"),
            "successful=", sum(1 for w in ws if w["kind"] == "socketio" and w.get("frames", 0) > 0),
        )
        print("bg task after text edit:", {k: (v["bg_ticks"], v["bg_status"]) for k, v in r.get("bg_after_text_edit", {}).items()})


if __name__ == "__main__":
    main()
