"""CMP-01 re-verify: raw multipart to /_upload with hostile filenames; prints where files landed.
Usage: hostile_upload.py <frontend_base> <backend_base> <state_handler_name>"""
import sys, time, json, httpx
from playwright.sync_api import sync_playwright
fe, be, handler = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/"), sys.argv[3]
names = ["../../evil1.txt", "..\\..\\evil2.txt", "/etc/evil3.txt", "C:\\evil4.txt", "...", "..", ". .", "sub/../../evil5.txt",
         "ünï cødé ☃.txt", "a/b/c.txt", "\u202etxt.exe", "%2e%2e%2fevil6.txt", "nul", ".hidden", "x" * 300 + ".txt"]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.goto(fe + "/upload"); pg.wait_for_selector("#page-upload"); time.sleep(2)
    token = pg.evaluate("() => window.sessionStorage.getItem('token')")
    files = [("files", (n, b"hostile-" + str(i).encode(), "text/plain")) for i, n in enumerate(names)]
    r = httpx.post(be + "/_upload", files=files, headers={"Reflex-Client-Token": token, "Reflex-Event-Handler": handler}, timeout=30)
    print("status", r.status_code, r.text[:300].replace("\n", " "))
    time.sleep(1.5)
    print(pg.inner_text("#uploaded")[:6000])
    b.close()
