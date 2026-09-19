"""Pure-reflex probe (NO reflex-enterprise, no shim): a downstream delta filter
drops an uncached computed var while the user is anonymous; once the filter
stops dropping it, does the value ever reach the client again?

Models exactly what reflex_enterprise.auth.enforcement.install_delta_filter does:
it wraps BaseState.get_delta and removes protected keys AFTER get_delta() ran.

Usage: python pure_delta_memo.py
"""
import asyncio
from importlib.metadata import version

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__
print("reflex from:", rx.__file__)
print("reflex version:", version("reflex"))

_SHARED = {"v": "default-shared"}
PROTECTED = "shared_label"
AUTHENTICATED = False


class ProbeState(rx.State):
    hits: int = 0

    @rx.var(cache=False)
    def shared_label(self) -> str:
        return f"shared={_SHARED['v']}"


# The enterprise-style delta filter: patch get_delta, drop protected keys after.
_orig_get_delta = rx.State.get_delta


def filtered_get_delta(self):
    delta = _orig_get_delta(self)
    if AUTHENTICATED:
        return delta
    return {
        sn: {k: v for k, v in sd.items() if PROTECTED not in k}
        for sn, sd in delta.items()
    }


rx.State.get_delta = filtered_get_delta


def sent(label, st):
    d = st.get_delta()
    has = any(PROTECTED in k for sd in d.values() for k in sd)
    print(f"{label:34s} client receives protected var: {str(has):5s}  delta={d}")
    st._clean()
    return has


async def main():
    global AUTHENTICATED
    st = ProbeState(_reflex_internal_init=True)

    st._mark_dirty()
    sent("1 anon initial", st)

    # anonymous PUBLIC handler changes the server-side data the protected var reads
    _SHARED["v"] = "SERVER-ONLY-SECRET"
    st.hits += 1
    sent("2 anon event (value changed)", st)

    # user logs in -> filter stops dropping the key
    AUTHENTICATED = True
    st.hits += 1
    got = sent("3 after login", st)

    st.hits += 1
    got2 = sent("4 after another event", st)

    print()
    print("EXPECTED: steps 3/4 deliver shared_label = shared=SERVER-ONLY-SECRET")
    print("RESULT  : step3 =", got, " step4 =", got2)


asyncio.run(main())
