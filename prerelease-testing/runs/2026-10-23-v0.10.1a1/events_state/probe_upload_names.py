"""CMP-01: POST raw multipart uploads with hostile filenames to /_upload; the handler logs name/path/target.

Usage: python probe_upload_names.py http://localhost:<BP> <handler full name> <form_log.jsonl>
"""
import http.client, json, sys, time, uuid, urllib.parse

base, handler, logpath = sys.argv[1], sys.argv[2], sys.argv[3]
u = urllib.parse.urlparse(base)
NAMES = [b"..", b"../../etc/passwd", b"....", b".. ", b"/abs/evil.txt", b"C:\\x\\y.txt", b"a/../../b.txt", b"a\\..\\..\\b.txt",
         b"sub/dir/file.txt", b"nul\x00byte.txt", b"ok.txt", b". .", b"..\\..\\x", b"~/x.txt", b"%2e%2e/%2e%2e/x", b"", b"\xff\xfeweird.txt"]
token = str(uuid.uuid4())
n0 = sum(1 for _ in open(logpath)) if __import__("os").path.exists(logpath) else 0
for name in NAMES:
    boundary = b"----qa" + uuid.uuid4().hex.encode()
    body = b"--" + boundary + b"\r\nContent-Disposition: form-data; name=\"files\"; filename=\"" + name.replace(b'"', b'\\"') + b"\"\r\nContent-Type: text/plain\r\n\r\nhello\r\n--" + boundary + b"--\r\n"
    c = http.client.HTTPConnection(u.hostname, u.port, timeout=20)
    c.request("POST", "/_upload", body=body, headers={"Content-Type": "multipart/form-data; boundary=" + boundary.decode(), "reflex-client-token": token, "reflex-event-handler": handler, "Content-Length": str(len(body))})
    r = c.getresponse(); data = r.read()
    print(f"{name!r:28} -> HTTP {r.status} {data[:100]!r}")
    c.close(); time.sleep(0.3)
time.sleep(1.5)
print("--- handler records")
for line in list(open(logpath))[n0:]:
    rec = json.loads(line)
    if rec.get("form") == "upload":
        print({k: rec.get(k) for k in ("filename", "name", "path", "target", "inside", "path_inside", "written", "error", "path_error")})
