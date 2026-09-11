"""FINDING-025 acceptance probe: admin pages, links, a real static asset, login, context.

Usage: probe_admin.py <base_url> <label> <out.json>
"""

import json
import re
import sys
import urllib.request

BASE, LABEL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
res = {"base": BASE, "label": LABEL, "routes": {}, "assets": {}, "links": []}


def get(path, follow=True):
    """Fetch a path and report status plus a body sample."""
    url = BASE + path
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "review"})
        opener = urllib.request.build_opener()
        if not follow:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, *a, **k):  # noqa: D102
                    return None
            opener = urllib.request.build_opener(NoRedirect)
        with opener.open(req, timeout=30) as r:
            body = r.read()
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # noqa: BLE001
        return f"<{type(e).__name__}>", b""


for path in ("/ping", "/admin", "/admin/", "/admin/widget/list", "/admin/widget/create", "/admin/login"):
    status, body = get(path)
    res["routes"][path] = {"status": status, "bytes": len(body),
                           "has_nomatchfound": b"NoMatchFound" in body}

_, admin_body = get("/admin/")
links = sorted(set(re.findall(rb'href="([^"]+)"', admin_body)))
res["links"] = [l.decode(errors="replace") for l in links][:20]

# fetch every static asset the admin page actually references
for link in res["links"]:
    if "/static/" in link:
        path = link.replace(BASE, "")
        status, body = get(path)
        res["assets"][path] = {"status": status, "bytes": len(body)}

with open(OUT, "w") as f:
    json.dump(res, f, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "links"}, indent=1)[:1600])
