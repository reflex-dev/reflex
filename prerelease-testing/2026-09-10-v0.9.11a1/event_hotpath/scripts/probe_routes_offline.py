"""Offline differential check of the route matcher (memoized per (path, frontend_path) in 0.9.11a1).

Run under each venv from a neutral cwd; prints JSON lines {path, frontend_path, route}. Compare outputs between versions.
Also exercises >4096 distinct paths (lru_cache maxsize) and re-checks a sample afterwards, and a frontend_path flip
on the same router object (cache key must include the prefix).

    <venv>/bin/python probe_routes_offline.py > out.jsonl
"""
from __future__ import annotations

import json
import sys

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__
from reflex.config import get_config  # noqa: E402
from reflex.route import get_router  # noqa: E402

# App.router passes page routes WITHOUT the leading slash ("index" for "/"), exactly as App._unevaluated_pages stores them
routes = ["index", *[f"static-{i}" for i in range(150)], "item/[id]", "docs/[[...splat]]", "posts/all/[x]",
          "posts/[id]", "apple", "app", "404", "a.b/[c]"]
router = get_router(routes)
paths = ["/", "", "/index", "/index/", "//", "/item/1", "/item/1/", "/item/2", "/item/a%20b", "/item/héllo", "/item/a.b",
         "/item/1/2", "/item", "/posts/all", "/posts/all/", "/posts/all/7", "/posts/42", "/posts/all/7/8", "/docs", "/docs/",
         "/docs/a", "/docs/a/b/c/", "/static-0", "/static-149", "/static-150", "/apple", "/app", "/app/apple", "/app/app",
         "/404", "/nonexistent", "/a.b/x", "/A.B/x", "/Item/1", "/x/y/z", "/static-7?q=1", "/item/1#frag", "/item/%2F", "/item/ "]
out = []
for p in paths:
    out.append({"path": p, "fp": "", "route": router(p)})
# frontend_path flip on the SAME router object
cfg = get_config()
old_fp = cfg.frontend_path
cfg.frontend_path = "/app"
for p in ["/app/item/1", "/app/apple", "/app/app", "/apple", "/app", "/item/1", "/app/", "/app", "/app/index", "/app/static-3"]:
    out.append({"path": p, "fp": "/app", "route": router(p)})
cfg.frontend_path = old_fp
# same paths again with no prefix (must equal the first block, not the /app block)
for p in ["/apple", "/app", "/item/1"]:
    out.append({"path": p, "fp": "(reset)", "route": router(p)})
# overflow the cache
for i in range(5000):
    assert router(f"/item/{i}") == "item/[id]", (i, router(f"/item/{i}"))
    assert router(f"/static-{i % 150}") == f"static-{i % 150}"
for p in ["/", "/item/1", "/posts/all", "/posts/all/7", "/docs/a/b", "/apple", "/app", "/static-149", "/nonexistent"]:
    out.append({"path": p, "fp": "(after 5000 distinct)", "route": router(p)})
for o in out:
    print(json.dumps(o, ensure_ascii=False))
print(json.dumps({"version": rx.constants.Reflex.VERSION, "python": sys.version.split()[0], "n": len(out)}), file=sys.stderr)
