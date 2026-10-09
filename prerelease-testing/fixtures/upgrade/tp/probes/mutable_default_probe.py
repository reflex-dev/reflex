"""F-009 at the framework level: reflex-chat does `cls.__fields__["messages"].default = initial_messages`.
Is a mutable list assigned as a Field default shared by every state instance (session)?

Usage: <venv>/bin/python mutable_default_probe.py <expected-venv-name>
"""
import sys

import reflex as rx

assert f"/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__


class Chatty(rx.State):
    messages: list[dict[str, str]] = []


def new_session():
    root = rx.State(_reflex_internal_init=True)
    return root.get_substate(Chatty.get_full_name().split(".")[1:])


initial = [{"role": "assistant", "content": "GREETING"}]
Chatty.__fields__["messages"].default = initial  # exactly what reflex-chat does (dunder attr access)
a, b = new_session(), new_session()
a.messages.append({"role": "user", "content": "typed-in-session-A"})
print("session A messages:", [m["content"] for m in a.messages])
print("session B messages:", [m["content"] for m in b.messages])
print("shared list object with the module-level `initial`:", initial is not None and [m["content"] for m in initial])
print("LEAK across sessions:", any(m["content"] == "typed-in-session-A" for m in b.messages))
