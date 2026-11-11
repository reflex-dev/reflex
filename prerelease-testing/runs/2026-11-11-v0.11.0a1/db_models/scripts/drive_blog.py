"""Drive the blog app: create data (mode=create) or verify existing data (mode=verify)."""
import sys

from pwlib import SHOTS, Cap, browser, check, text, wait_text

base = sys.argv[1]
mode = sys.argv[2]
tag = sys.argv[3]
cap = Cap()
with browser() as b:
    page = b.new_page()
    cap.attach(page)
    page.goto(base + "/")
    page.wait_for_selector("text=Blog")
    page.wait_for_timeout(1500)
    if mode == "create":
        for name, email, city, role in [("alice", "a@x.io", "Paris", "editor"), ("bob", "", "Oslo", "writer")]:
            page.fill("#a_name", name); page.fill("#a_email", email); page.fill("#a_city", city); page.fill("#a_role", role)
            page.click("#add_author"); wait_text(page, "#msg", f"added author {name}")
        # duplicate unique name
        page.fill("#a_name", "alice"); page.click("#add_author"); wait_text(page, "#msg", "error")
        check("unique violation surfaced", True, text(page, "#msg"))
        for author, title, tags in [("alice", "Hello World", "news, intro"), ("bob", "Second post", "intro"), ("alice", "Third", "")]:
            page.fill("#p_author", author); page.fill("#p_title", title); page.fill("#p_body", f"body of {title}"); page.fill("#p_tags", tags)
            page.click("#add_post"); wait_text(page, "#msg", f"added post {title}")
        page.wait_for_timeout(800)
    if mode == "create2":
        page.fill("#a_name", "carol"); page.fill("#a_email", "c@x.io"); page.fill("#a_city", "Rome"); page.fill("#a_role", "editor")
        page.click("#add_author"); wait_text(page, "#msg", "added author carol")
        page.fill("#a_name", "carol"); page.click("#add_author"); wait_text(page, "#msg", "error")
        check("unique violation surfaced (new)", True, text(page, "#msg"))
        page.fill("#p_author", "carol"); page.fill("#p_title", "Carol post"); page.fill("#p_body", "b"); page.fill("#p_tags", "news, fresh")
        page.click("#add_post"); wait_text(page, "#msg", "added post Carol post")
        page.wait_for_timeout(800)
    rows = page.query_selector_all(".post-row")
    rtxt = [r.inner_text().replace("\n", " ") for r in rows]
    print("POSTS:", rtxt)
    atxt = [r.inner_text() for r in page.query_selector_all(".author-row")]
    print("AUTHORS:", atxt)
    check("3 posts listed", len(rows) >= 3, str(len(rows)))
    check("tags rendered", any("news" in r and "intro" in r for r in rtxt))
    check("author names rendered", any("by alice" in r for r in rtxt))
    page.screenshot(path=f"{SHOTS}/{tag}_index.png", full_page=True)
    page.click("text=Hello World")
    wait_text(page, "#d_title", "Hello World")
    page.wait_for_timeout(800)
    det = {k: text(page, f"#{k}") for k in ["d_title", "d_body", "d_author", "d_created", "d_joined", "d_city", "d_tags"]}
    print("DETAIL:", det)
    check("detail author+role", "alice" in det["d_author"] and "editor" in det["d_author"], det["d_author"])
    check("detail city JSON", "Paris" in det["d_city"], det["d_city"])
    check("detail tags", "news" in det["d_tags"] and "intro" in det["d_tags"], det["d_tags"])
    if page.query_selector("#bump"):
        v0 = text(page, "#d_views")
        page.click("#bump")
        page.wait_for_function("(v) => document.querySelector('#d_views').innerText != v", arg=v0, timeout=10000)
        check("bump views", True, v0 + " -> " + text(page, "#d_views"))
    page.screenshot(path=f"{SHOTS}/{tag}_detail.png", full_page=True)
    # direct navigation to dynamic route
    page.goto(base + "/post/2")
    wait_text(page, "#d_title", "Second post")
    check("direct nav /post/2", True)
    page.goto(base + "/post/999")
    page.wait_for_timeout(2500)
    check("missing post shows fallback", page.query_selector("#d_missing") is not None)
cap.report()
