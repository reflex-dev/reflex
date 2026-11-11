"""Drive the ser app: serializer checks in Chromium."""
import sys

from pwlib import SHOTS, Cap, browser, check, text, wait_text

base, tag = sys.argv[1], sys.argv[2]
legacy = len(sys.argv) > 3 and sys.argv[3] == "legacy"
cap = Cap()


def all_text(page, sel):
    return [e.inner_text().replace("\n", " ") for e in page.query_selector_all(sel)]


with browser() as b:
    ctx = b.new_context()
    page = ctx.new_page()
    cap.attach(page, "t1:")
    page.goto(base + "/")
    page.wait_for_selector("#seed")
    page.wait_for_timeout(1500)
    page.click("#seed")
    wait_text(page, "#msg", "seeded")
    page.wait_for_selector(".post")
    page.wait_for_timeout(500)
    posts = all_text(page, ".post")
    print("POSTS:", posts)
    check("post 1 head", any("First by alice / ALICE" in p for p in posts), posts[0] if posts else "")
    check("flags length + nested flag.user", any("2 flags" in p and "spam? from bob" in p for p in posts))
    tags = all_text(page, ".p-tag")
    print("TAGS:", tags)
    if legacy:
        check("legacy user serializer used for Tag", any(t.startswith("LEGACY:") for t in tags), str(tags))
    else:
        check("m2m tags", "news" in tags and "misc" in tags, str(tags))
    u = text(page, "#user")
    print("USER:", u)
    check("synonym .upper()", "nick upper: ALICE" in u, u)
    check("hybrid_property rendered", "hybrid: [ALICE]" in u, u)
    check("column_property rendered", "name_len: [5]" in u, u)
    check("computed var returning model", "top: First by alice" in text(page, "#top"), text(page, "#top"))
    check("computed list[str] from models", "First,Second" in text(page, "#titles"), text(page, "#titles"))
    page.screenshot(path=f"{SHOTS}/{tag}_index.png", full_page=True)

    # second tab
    page2 = ctx.new_page()
    cap.attach(page2, "t2:")
    page2.goto(base + "/")
    page2.wait_for_selector(".post")
    page2.fill("#new_title", "From tab2")
    page2.click("#add")
    page2.wait_for_function("() => [...document.querySelectorAll('.p-head')].some(e => e.innerText.includes('From tab2'))", timeout=10000)
    check("tab2 add post", True)
    page.click("#load")
    page.wait_for_function("() => [...document.querySelectorAll('.p-head')].some(e => e.innerText.includes('From tab2'))", timeout=10000)
    check("tab1 sees tab2 post after reload", True)
    page2.close()

    # mutation of a model held in state
    page.click("#mutate")
    page.wait_for_timeout(1500)
    heads = all_text(page, ".p-head")
    u = text(page, "#user")
    check("mutate post title in state -> UI updates", any("MUTATED" in h for h in heads), heads[0])
    check("mutate user.username in state -> UI updates", "alice-mutated" in u, u)
    check("mutation -> computed var top_post updates", "MUTATED" in text(page, "#top"), text(page, "#top"))
    page.click("#append")
    page.wait_for_timeout(1500)
    check("append to post.tags in state -> UI updates", "appended" in all_text(page, ".p-tag"), str(all_text(page, ".p-tag")))
    page.click("#load")
    page.wait_for_timeout(1500)
    page.click("#rename")
    page.wait_for_function("() => document.querySelector('.p-head').innerText.includes('First!')", timeout=10000)
    check("rename via DB + reload", True)

    page.click("#bg")
    wait_text(page, "#msg", "bg loaded")
    page.wait_for_timeout(500)
    bg = all_text(page, ".bg-row")
    check("background task loads models", len(bg) >= 3 and "alice" in bg[0], str(bg))

    page.click("#sync")
    page.wait_for_timeout(2000)
    print("MSG after sync:", text(page, "#msg"))
    sr = all_text(page, ".sync-row")
    print("SYNC rows:", sr)
    check("sync rx.session() with Base models renders", len(sr) >= 3, str(sr))
    check("sync: lazily loaded user shown", "sync lazy user: alice" in text(page, "#msg"), text(page, "#msg"))
    check("sync: user relationship (lazy loaded in session) serialized for first row", "| alice" in (sr[0] if sr else ""), sr[0] if sr else "")

    page.click("#asess")
    page.wait_for_timeout(2000)
    print("MSG after asession:", text(page, "#msg"))
    ar = all_text(page, ".as-row")
    check("rx.asession()", len(ar) >= 3, str(ar))

    page.click("#expired")
    page.wait_for_timeout(2000)
    print("EXPIRED:", text(page, "#exp"), "| msg:", text(page, "#msg"))
    check("expire_on_commit=True: user renders (expected blank per design)", "bob" in text(page, "#exp"), text(page, "#exp"))
    page.screenshot(path=f"{SHOTS}/{tag}_after_actions.png", full_page=True)

    page.click("#to_detail")
    wait_text(page, "#d_title", "First")
    check("detail Post|None via client nav", "alice" in text(page, "#d_user"))
    page.goto(base + "/detail/2")
    wait_text(page, "#d_title", "Second")
    check("detail direct nav", True)

    # reload: state restored from the state manager (pickled models under redis/disk)
    page.goto(base + "/")
    page.wait_for_selector(".post")
    page.wait_for_timeout(2500)
    bg2, as2, sy2 = all_text(page, ".bg-row"), all_text(page, ".as-row"), all_text(page, ".sync-row")
    print("AFTER RELOAD bg/as/sync:", bg2, as2, sy2)
    check("state restored after reload (bg_posts with user)", len(bg2) >= 3 and "| alice" in bg2[0], str(bg2))
    check("state restored after reload (as_posts)", len(as2) >= 3, str(as2))
    p3 = ctx.new_page()
    cap.attach(p3, "soft:")
    p3.goto(base + "/unloaded_soft")
    p3.wait_for_selector("#soft")
    p3.wait_for_timeout(2500)
    ur = all_text(p3, ".u-row")
    print("SOFT rows:", ur)
    check("unloaded relationship -> blank username", len(ur) >= 2 and "by []" in ur[0], str(ur))
    p3.screenshot(path=f"{SHOTS}/{tag}_unloaded_soft.png", full_page=True)
    p4 = ctx.new_page()
    cap.attach(p4, "hard:")
    p4.goto(base + "/unloaded_hard")
    p4.wait_for_timeout(4000)
    body = p4.inner_text("body")[:500]
    print("HARD body:", body.replace("\n", " | "))
    p4.screenshot(path=f"{SHOTS}/{tag}_unloaded_hard.png", full_page=True)
cap.report()
