"""Models in state across a dev hot reload (disk state manager)."""
import subprocess
import sys
import time

from pwlib import Cap, browser, check, wait_text

base, touch = sys.argv[1], sys.argv[2]
cap = Cap()
with browser() as b:
    page = b.new_page()
    cap.attach(page)
    page.goto(base + "/")
    page.wait_for_selector("#seed")
    page.wait_for_timeout(1500)
    page.click("#seed")
    page.wait_for_selector(".post")
    page.click("#bg")
    wait_text(page, "#msg", "bg loaded")
    before = [e.inner_text() for e in page.query_selector_all(".bg-row")]
    with open(touch, "a") as f:
        f.write(f"\n# touched {time.time()}\n")
    time.sleep(12)
    page.click("#mutate")  # an event after the reload
    page.wait_for_timeout(3000)
    after = [e.inner_text() for e in page.query_selector_all(".bg-row")]
    heads = [e.inner_text() for e in page.query_selector_all(".p-head")]
    print("before", before, "after", after, "heads", heads[:1])
    check("bg_posts survive hot reload", before == after and len(after) >= 2)
    check("event after hot reload mutates models", any("MUTATED" in h for h in heads))
    page.reload()
    page.wait_for_selector(".post")
    page.wait_for_timeout(2500)
    after2 = [e.inner_text() for e in page.query_selector_all(".bg-row")]
    check("bg_posts after hot reload + page reload", after2 == before, str(after2))
cap.report()
