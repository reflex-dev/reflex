"""#7493 probe: does re-marking client-storage vars dirty at boot re-run (and re-send) computed vars that depend on them?

Page `/` renders a LocalStorage var `tok` (key `bd_tok`), a cached computed var on it in the same state (`derived`),
one in a substate (`sub_derived`, cross-state dependency via get_state-free inheritance) and an expensive-looking
cached var (`lookup`, stands in for reflex-local-auth's `authenticated_user` DB query / google-auth's tokeninfo).
Every computed-var evaluation prints `BOOTDUP eval <name> #<n> tok=<value>` to the server log; an on_load counts too.
"""

import time

import reflex as rx

# venv guard (a3_events_tp): bin/start.sh exports EV_EXPECT_VENV=<venv name>
_EXPECT_VENV = __import__("os").environ.get("EV_EXPECT_VENV", "")
assert _EXPECT_VENV and f"/scratchpad/envs/{_EXPECT_VENV}/" in rx.__file__, (rx.__file__, _EXPECT_VENV)
print(f"VENV_GUARD ok venv={_EXPECT_VENV} reflex={rx.__file__}", flush=True)

N = {"derived": 0, "lookup": 0, "sub_derived": 0, "on_load": 0}


def ev(name: str, tok: str) -> None:
    N[name] += 1
    print(f"BOOTDUP {time.time():.3f} eval {name} #{N[name]} tok={tok!r}", flush=True)


class TokState(rx.State):
    tok: str = rx.LocalStorage(name="bd_tok")
    plain: str = "p"

    @rx.var
    def derived(self) -> str:
        ev("derived", self.tok)
        return self.tok.upper()

    @rx.var
    def lookup(self) -> str:
        ev("lookup", self.tok)
        return f"user-for-{self.tok}" if self.tok else "anonymous"

    @rx.event
    def load(self):
        ev("on_load", self.tok)

    @rx.event
    def set_tok(self, v: str):
        self.tok = v


class TokSub(TokState):
    @rx.var
    def sub_derived(self) -> str:
        ev("sub_derived", self.tok)
        return f"sub:{self.tok}"


def index() -> rx.Component:
    return rx.vstack(
        rx.text(rx.State.router.session.client_token, id="token"),
        rx.text("tok=", TokState.tok, id="tok"),
        rx.text("derived=", TokState.derived, id="derived"),
        rx.text("lookup=", TokState.lookup, id="lookup"),
        rx.text("sub=", TokSub.sub_derived, id="sub"),
        rx.button("set", id="set", on_click=TokState.set_tok("from-click")),
    )


app = rx.App()
app.add_page(index, route="/", on_load=TokState.load)
