"""reflex-chat: does a message typed in one browser session show up in another session?

Usage: drive_chat_leak.py <base_url> <tag>
"""
import sys

from tpdrive import browser, wait_text

BASE = sys.argv[1].rstrip("/")
TAG = sys.argv[2]


def send(b, route, msg):
    ctx = b.new_context()
    p = ctx.new_page()
    p.goto(BASE + route, wait_until="networkidle")
    wait_text(p, "#page_title", route)
    p.wait_for_timeout(800)
    p.fill("input[placeholder='Type something...']", msg)
    p.get_by_role("button", name="Send").click()
    wait_text(p, "body", "Pass the")
    p.wait_for_timeout(800)
    body = p.locator("body").inner_text()
    ctx.close()
    return body


def look(b, route):
    ctx = b.new_context()
    p = ctx.new_page()
    p.goto(BASE + route, wait_until="networkidle")
    wait_text(p, "#page_title", route)
    p.wait_for_timeout(1500)
    body = p.locator("body").inner_text()
    ctx.close()
    return body


with browser() as b:
    before_plain = look(b, "/chat")
    before_init = look(b, "/chat-initial")
    send(b, "/chat-initial", f"from-A-initial-{TAG}")
    send(b, "/chat", f"from-A-plain-{TAG}")
    after_init = look(b, "/chat-initial")
    after_plain = look(b, "/chat")
    print("fresh /chat shows INITIAL-GREETING:", "INITIAL-GREETING" in before_plain)
    print("fresh /chat-initial shows INITIAL-GREETING:", "INITIAL-GREETING" in before_init)
    print(f"session B /chat-initial sees session A's /chat-initial message: {f'from-A-initial-{TAG}' in after_init}")
    print(f"session B /chat sees session A's /chat message: {f'from-A-plain-{TAG}' in after_plain}")
    print(f"session B /chat sees session A's /chat-initial message: {f'from-A-initial-{TAG}' in after_plain}")
    print("--- /chat-initial body in session B ---")
    print(after_init[-400:])
