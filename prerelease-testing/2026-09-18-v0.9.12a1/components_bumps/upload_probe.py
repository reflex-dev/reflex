"""Probe the /_upload endpoint for controlled 400s (#6860)."""
import json, sys
import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8300"
files = {"files": ("a.txt", b"hello", "text/plain")}
cases = [
    ("unknown handler", {"reflex-client-token": "tok-123", "reflex-event-handler": "gallery.gallery.UploadState.nope"}),
    ("missing handler header", {"reflex-client-token": "tok-123"}),
    ("missing token header", {"reflex-event-handler": "gallery.gallery.UploadState.handle_upload"}),
    ("empty handler", {"reflex-client-token": "tok-123", "reflex-event-handler": ""}),
    ("weird handler", {"reflex-client-token": "tok-123", "reflex-event-handler": "../../etc/passwd"}),
    ("valid handler bad token", {"reflex-client-token": "not-a-real-token", "reflex-event-handler": "gallery.gallery.UploadState.handle_upload"}),
]
out = []
with httpx.Client(timeout=20.0, trust_env=False) as c:
    for name, headers in cases:
        try:
            r = c.post(f"{BASE}/_upload", files=files, headers=headers)
            body = r.text[:300]
            out.append({"case": name, "status": r.status_code, "body": body})
        except Exception as e:
            out.append({"case": name, "error": repr(e)})
print(json.dumps(out, indent=2))
