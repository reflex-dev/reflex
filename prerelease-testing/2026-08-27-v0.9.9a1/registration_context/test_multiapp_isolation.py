"""Test (b) part 1: two rx.App instances in one process via RegistrationContext.

Run:
    REFLEX_TELEMETRY_ENABLED=false <venv>/bin/python test_multiapp_isolation.py

Checks (each prints PASS/FAIL/ANOMALY):
 1. Second App() in the same RegistrationContext raises ReflexRuntimeError w/ fork guidance.
 2. fork() + set as current -> second App can be created.
 3. @rx.page registered BEFORE fork carries into fork (documented: fork preserves registrations).
 4. @rx.page registered AFTER fork in the fork does NOT leak back into the original context.
 5. add_page() pages do not bleed between apps (_unevaluated_pages disjoint).
 6. States defined while fork active register on fork only, not on original.
 7. get_config() cache is per-context: fork gets a fresh Config instance.
 8. bundle_library() while fork active does not mutate original context's list.
"""

import sys

results = []


def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    results.append((status, name, detail))
    print(f"[{status}] {name} {('- ' + detail) if detail else ''}")


import reflex as rx
from reflex_base.registry import RegistrationContext
from reflex_base.utils.exceptions import ReflexRuntimeError

ctx1 = RegistrationContext.ensure_context()


class StateOne(rx.State):
    value: str = "one"


@rx.page(route="/page-before-fork", title="BeforeFork")
def page_before_fork():
    return rx.text("before fork")


app1 = rx.App()
app1.add_page(lambda: rx.text("app1 index"), route="/", title="App1")
app1._apply_decorated_pages()

check(
    "app1 owns before-fork page",
    "page-before-fork" in app1._unevaluated_pages and "index" in app1._unevaluated_pages,
    f"routes={sorted(app1._unevaluated_pages)}",
)

# 1. second App in same context must be rejected with actionable message
try:
    rx.App()
    check("second App() in same ctx raises", False, "no exception raised!")
except ReflexRuntimeError as e:
    check(
        "second App() in same ctx raises ReflexRuntimeError",
        "fork()" in str(e),
        f"msg mentions fork(): {'fork()' in str(e)}",
    )
except Exception as e:  # noqa: BLE001
    check("second App() in same ctx raises", False, f"wrong exc type {type(e).__name__}: {e}")

# 2. fork and create app2
ctx2 = ctx1.fork()
token = RegistrationContext.set(ctx2)

@rx.page(route="/page-after-fork", title="AfterFork")
def page_after_fork():
    return rx.text("after fork")


class StateTwo(rx.State):
    value: str = "two"


app2 = rx.App()
app2.add_page(lambda: rx.text("app2 index"), route="/", title="App2")
app2._apply_decorated_pages()

check("app2 created after fork", app2 is not None)
check(
    "ctx2.app is app2 / ctx1.app is app1",
    ctx2.app is app2 and ctx1.app is app1,
)

# 3. before-fork page carried into fork (registrations preserved)
check(
    "before-fork @rx.page carried into fork (documented)",
    "page-before-fork" in app2._unevaluated_pages,
    f"app2 routes={sorted(app2._unevaluated_pages)}",
)

# 4. after-fork page NOT in ctx1
ctx1_routes = [kw.get("route") for _fn, kw in ctx1.decorated_pages]
check(
    "after-fork @rx.page did NOT leak to original ctx",
    "/page-after-fork" not in ctx1_routes,
    f"ctx1 decorated routes={ctx1_routes}",
)

# 5. add_page pages don't bleed
check(
    "add_page() no bleed",
    app1._unevaluated_pages["index"].title == "App1"
    and app2._unevaluated_pages["index"].title == "App2",
)

# 6. state registration isolation
check(
    "StateTwo registered on ctx2 only",
    StateTwo.get_full_name() in ctx2.base_states
    and StateTwo.get_full_name() not in ctx1.base_states,
    f"ctx1 has StateTwo: {StateTwo.get_full_name() in ctx1.base_states}",
)
check(
    "StateOne carried into ctx2 (fork preserves registrations)",
    StateOne.get_full_name() in ctx2.base_states,
)

# 7. per-context config
from reflex.config import get_config

cfg2 = get_config()
RegistrationContext.reset(token)
cfg1 = get_config()
check(
    "get_config() cached per-context (different instances)",
    cfg1 is not cfg2,
    f"id(cfg1)={id(cfg1):#x} id(cfg2)={id(cfg2):#x}",
)

# 8. bundled library isolation
from reflex.components.dynamic import bundle_library

tok2 = RegistrationContext.set(ctx2)
bundle_library("fork-only-lib")
RegistrationContext.reset(tok2)
check(
    "bundle_library in fork does not touch original",
    "fork-only-lib" in ctx2.bundled_libraries
    and "fork-only-lib" not in ctx1.bundled_libraries,
    f"ctx1={ctx1.bundled_libraries}",
)

fails = [r for r in results if r[0] == "FAIL"]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
sys.exit(1 if fails else 0)
