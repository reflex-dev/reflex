"""F1 verifier combo app: which state shapes make alpha's first load write client-storage defaults.

Each state uses distinct storage key names so one page load shows, per state, whether it was sent in full
and whether its storage defaults were written to the browser.
"""

import time
import uuid

import reflex as rx

assert "/envs/alpha/" in rx.__file__ or "/envs/stable/" in rx.__file__, rx.__file__


class Plain(rx.State):
    """Storage only, deterministic defaults."""

    pl_ls: str = rx.LocalStorage("pl-light", name="pl_ls")
    pl_ck: str = rx.Cookie("pl-unset", name="pl_ck")
    pl_ss: str = rx.SessionStorage("pl-x", name="pl_ss")


class WithUuid(rx.State):
    """Storage + a default_factory=uuid var in the SAME state (the claimed trigger); also a sync=True var."""

    wu_ls: str = rx.LocalStorage("wu-light", name="wu_ls")
    wu_ck: str = rx.Cookie("wu-unset", name="wu_ck", max_age=600)
    wu_ss: str = rx.SessionStorage("wu-x", name="wu_ss")
    wu_sync: str = rx.LocalStorage("wu-sync-default", name="wu_sync", sync=True)
    wu_id: str = rx.field(default_factory=lambda: uuid.uuid4().hex)

    @rx.event
    def set_sync(self, v: str):
        self.wu_sync = v


class ParentUuid(rx.State):
    """A parent with a per-instance default and no storage."""

    pu_id: str = rx.field(default_factory=lambda: uuid.uuid4().hex)


class ChildStorage(ParentUuid):
    """Storage only (deterministic) on a SUBSTATE whose parent is sent in full."""

    cs_ls: str = rx.LocalStorage("cs-light", name="cs_ls")
    cs_ck: str = rx.Cookie("cs-unset", name="cs_ck")
    cs_ss: str = rx.SessionStorage("cs-x", name="cs_ss")


class ParentPlain(rx.State):
    """Deterministic parent."""

    pp_n: int = 0


class ChildStorageUuid(ParentPlain):
    """Storage + uuid factory on a SUBSTATE only (parent deterministic)."""

    cu_ls: str = rx.LocalStorage("cu-light", name="cu_ls")
    cu_ck: str = rx.Cookie("cu-unset", name="cu_ck")
    cu_ss: str = rx.SessionStorage("cu-x", name="cu_ss")
    cu_id: str = rx.field(default_factory=lambda: uuid.uuid4().hex)


class WithSet(rx.State):
    """Storage + a set[str] default (serialized as list(set) -> order depends on PYTHONHASHSEED)."""

    ws_ls: str = rx.LocalStorage("ws-light", name="ws_ls")
    ws_tags: set[str] = {"alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta"}


class WithClockVar(rx.State):
    """Storage + a cached computed var whose value depends on the clock."""

    wt_ls: str = rx.LocalStorage("wt-light", name="wt_ls")

    @rx.var
    def wt_stamp(self) -> str:
        return str(time.time_ns())


def index() -> rx.Component:
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd-flag"),
        rx.text(Plain.pl_ls, id="pl-ls"),
        rx.text(WithUuid.wu_ls, id="wu-ls"),
        rx.text(WithUuid.wu_sync, id="wu-sync"),
        rx.text(WithUuid.wu_id, id="wu-id"),
        rx.text(ChildStorage.cs_ls, id="cs-ls"),
        rx.text(ChildStorageUuid.cu_ls, id="cu-ls"),
        rx.text(WithSet.ws_ls, id="ws-ls"),
        rx.text(WithSet.ws_tags.to_string(), id="ws-tags"),
        rx.text(WithClockVar.wt_ls, id="wt-ls"),
        rx.text(WithClockVar.wt_stamp, id="wt-stamp"),
        rx.button("sync A", on_click=WithUuid.set_sync("sync-from-tabA"), id="set-sync-a"),
    )


app = rx.App()
app.add_page(index)
