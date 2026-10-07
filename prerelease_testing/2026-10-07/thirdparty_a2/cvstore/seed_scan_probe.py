"""Per-process probe: does a normal-event delta (get_delta) carry the value a cached computed var
wrote back into a client-storage var, or the stale one? Mirrors what 0.9.12's update_vars_internal
event delta did (and what 0.10.0a1 still does for update_vars_internal on client-side navigation).

Usage: PYTHONHASHSEED=<n> <venv>/bin/python seed_scan_probe.py <venv-name>   (run from a neutral dir)
Do NOT add -I or -E: both make Python ignore PYTHONHASHSEED, so every run gets a random seed.
Prints: seed=<n> tp:<order> a:<order> f:<order> ga:<order>
"""
import asyncio
import json
import os
import sys

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__


class StoreState(rx.State):  # same var names as tp_patterns StoreState
    ls_cv: str = rx.LocalStorage(name="tp_ls_cv")
    ls_onload: str = rx.LocalStorage(name="tp_ls_onload")
    ls_event: str = rx.LocalStorage(name="tp_ls_event")
    ls_nd: str = rx.LocalStorage(name="tp_ls_nd")
    ck_onload: str = rx.Cookie(name="tp_ck_onload")
    log: list[str] = []

    @rx.var(cache=True)
    def cv_check(self) -> str:
        if self.ls_cv == "bad":
            self.ls_cv = ""
            return "cleared-in-computed-var"
        return f"value={self.ls_cv!r}"


class ACachedCv(rx.State):  # same var names as my cvstore (a)
    ls: str = rx.LocalStorage(name="v_a")
    seen: str = ""
    noop_count: int = 0

    @rx.var(cache=True)
    def check(self) -> str:
        if self.ls == "bad":
            self.ls = ""
            return "cleared-by-cached-cv"
        return f"value={self.ls!r}"


class GoogleAuthLike(rx.State):  # reflex-google-auth GoogleAuthState var names/shape (no network)
    token_response_json: str = rx.LocalStorage()
    refresh_token: str = rx.LocalStorage()

    @rx.var
    def id_token_json(self) -> str:
        return self.token_response_json[:3]

    @rx.var(cache=True)
    def client_id(self) -> str:
        return "x"

    @rx.var
    def scopes(self) -> list[str]:
        return []

    @rx.var
    def access_token(self) -> str:
        return self.token_response_json[:2]

    @rx.var
    def id_token(self) -> str:
        return self.token_response_json[:1]

    @rx.var(cache=True)
    def tokeninfo(self) -> dict[str, str]:
        if self.token_response_json and self.id_token:
            self.token_response_json = ""
        return {}

    @rx.var(cache=False)
    def token_is_valid(self) -> bool:
        return bool(self.tokeninfo)

    @rx.var(cache=True)
    def user_name(self) -> str:
        return self.tokeninfo.get("name", "")

    @rx.var(cache=True)
    def user_email(self) -> str:
        return self.tokeninfo.get("email", "")


async def one(cls, var, bad):
    root = rx.State(_reflex_internal_init=True)
    s = root.get_substate(cls.get_full_name().split(".")[1:])
    # settle all computed vars first (the hydrate snapshot of 0.9.12 did this with the reset default)
    root.dict()
    root._clean()
    setattr(s, var, bad)  # what update_vars_internal does
    d = root.get_delta()
    if asyncio.iscoroutine(d):
        d = await d
    sub = d.get(cls.get_full_name(), {})
    sent = sub.get(var + "_rx_state_", "<absent>")
    return ("FRESH" if sent == "" else "STALE"), list(sub)[:3]


async def main():
    res = {}
    for name, cls, var, bad in [
        ("tp", StoreState, "ls_cv", "bad"),
        ("a", ACachedCv, "ls", "bad"),
        ("ga", GoogleAuthLike, "token_response_json", '{"id_token": "x"}'),
    ]:
        res[name] = (await one(cls, var, bad))[0]
    print(f"seed={os.environ.get('PYTHONHASHSEED')} " + " ".join(f"{k}:{v}" for k, v in res.items()))


asyncio.run(main())
