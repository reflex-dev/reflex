"""#7230 exploration: nested writes through `self.router` must obey the calling
StateProxy / ReadOnlyStateProxy mutation guard.

Every button appends a one-line result to `RootS.log`; the driver reads the
rendered log, the websocket deltas and the server log.
"""

import asyncio

import reflex as rx


def fmt(e: BaseException) -> str:
    """Format an exception as module.Name: message.

    Args:
        e: the exception.

    Returns:
        The formatted string.
    """
    return f"{type(e).__module__}.{type(e).__name__}: {str(e)[:110]}"


class RootS(rx.State):
    """Root state: router lives here."""

    log: list[str] = []
    ticks: int = 0
    onload_note: str = ""

    @rx.var
    def route_view(self) -> str:
        """Computed var reading the router (must keep working).

        Returns:
            route id + path + params.
        """
        return (
            f"route_id={self.router.route_id} path={self.router.url.path} "
            f"params={dict(self.router.page.params)}"
        )

    @rx.event
    def on_load_probe(self):
        """on_load reads the router."""
        self.onload_note = (
            f"on_load saw path={self.router.url.path} "
            f"raw_headers_n={len(self.router.headers.raw_headers)}"
        )

    @rx.event
    def clear(self):
        """Clear the log."""
        self.log = []

    # ---- (c) plain (foreground) event handler ----
    @rx.event
    def plain_rw(self):
        """A plain handler reads and writes router containers normally."""
        self.log.append(
            f"[plain] read path={self.router.url.path!r} "
            f"params={dict(self.router.page.params)!r}"
        )
        try:
            self.router.page.params["plain"] = "yes"
            self.log.append(f"[plain] write params OK -> {dict(self.router.page.params)!r}")
        except Exception as e:  # noqa: BLE001
            self.log.append("[plain] write params RAISED " + fmt(e))
        try:
            self.router.headers.raw_headers["x-plain"] = "1"
            self.log.append("[plain] write raw_headers OK")
        except Exception as e:  # noqa: BLE001
            self.log.append("[plain] write raw_headers RAISED " + fmt(e))
        try:
            self.router.url = "http://example.test/nope"
            self.log.append("[plain] `self.router.url = ...` ALLOWED")
        except Exception as e:  # noqa: BLE001
            self.log.append("[plain] `self.router.url = ...` RAISED " + fmt(e))

    # ---- (a) background handler, root state ----
    @rx.event(background=True)
    async def bg_root(self):
        """Background handler: outside must raise, inside must be allowed."""
        results: list[str] = []
        # direct field write outside the context (the reference behaviour)
        try:
            self.ticks = 1
            results.append("[bg-root] OUTSIDE direct field write ALLOWED (!)")
        except Exception as e:  # noqa: BLE001
            results.append("[bg-root] OUTSIDE direct field write " + fmt(e))
        # nested router container write outside the context
        try:
            self.router.page.params["bg"] = "outside"
            results.append("[bg-root] OUTSIDE router params write ALLOWED (!)")
        except Exception as e:  # noqa: BLE001
            results.append("[bg-root] OUTSIDE router params write " + fmt(e))
        try:
            self.router.headers.raw_headers["x-bg"] = "outside"
            results.append("[bg-root] OUTSIDE router raw_headers write ALLOWED (!)")
        except Exception as e:  # noqa: BLE001
            results.append("[bg-root] OUTSIDE router raw_headers write " + fmt(e))
        try:
            self.router.url = "http://example.test/outside"
            results.append("[bg-root] OUTSIDE `router.url = ...` ALLOWED (!)")
        except Exception as e:  # noqa: BLE001
            results.append("[bg-root] OUTSIDE `router.url = ...` " + fmt(e))
        # legacy alias
        try:
            self.router.page.params["legacy"] = "outside"
            results.append("[bg-root] OUTSIDE router.page.params ALLOWED (!)")
        except Exception as e:  # noqa: BLE001
            results.append("[bg-root] OUTSIDE router.page.params " + fmt(e))

        escaped = None
        async with self:
            try:
                self.router.page.params["bg"] = "inside"
                results.append(
                    f"[bg-root] INSIDE router params write OK -> "
                    f"{dict(self.router.page.params)!r}"
                )
            except Exception as e:  # noqa: BLE001
                results.append("[bg-root] INSIDE router params write RAISED " + fmt(e))
            try:
                self.router.headers.raw_headers["x-bg"] = "inside"
                results.append("[bg-root] INSIDE raw_headers write OK")
            except Exception as e:  # noqa: BLE001
                results.append("[bg-root] INSIDE raw_headers write RAISED " + fmt(e))
            dirty = sorted(self.dirty_vars)
            results.append(f"[bg-root] INSIDE dirty_vars={dirty}")
            escaped = self.router.page.params
            self.ticks += 1
            self.log.extend(results)
            results = []

        # the reference captured inside must not be writable after the block
        try:
            escaped["after"] = "1"
            results.append("[bg-root] ESCAPED reference write ALLOWED (!)")
        except Exception as e:  # noqa: BLE001
            results.append("[bg-root] ESCAPED reference write " + fmt(e))

        # (d) ReadOnlyStateProxy via rx.get_state
        token = self.router.session.client_token
        try:
            ro = await rx.get_state(token, RootS)
            try:
                ro.router.page.params["ro"] = "1"
                results.append("[bg-root] READONLY router params write ALLOWED (!)")
            except Exception as e:  # noqa: BLE001
                results.append("[bg-root] READONLY router params write " + fmt(e))
            try:
                ro.router.headers.raw_headers["ro"] = "1"
                results.append("[bg-root] READONLY raw_headers write ALLOWED (!)")
            except Exception as e:  # noqa: BLE001
                results.append("[bg-root] READONLY raw_headers write " + fmt(e))
            results.append(
                f"[bg-root] READONLY read ok: path={ro.router.url.path!r} "
                f"params={dict(ro.router.page.params)!r}"
            )
            try:
                ro.ticks = 99
                results.append("[bg-root] READONLY direct field write ALLOWED (!)")
            except Exception as e:  # noqa: BLE001
                results.append("[bg-root] READONLY direct field write " + fmt(e))
        except Exception as e:  # noqa: BLE001
            results.append("[bg-root] rx.get_state FAILED " + fmt(e))

        async with self:
            self.log.extend(results)

    # ---- (e) background read-only access outside the block still works ----
    @rx.event(background=True)
    async def bg_reads(self):
        """Reading router values outside the context must keep working."""
        out = []
        try:
            out.append(
                f"[bg-read] path={self.router.url.path!r} "
                f"route_id={self.router.route_id!r} "
                f"params={dict(self.router.page.params)!r} "
                f"token_len={len(self.router.session.client_token)} "
                f"headers_n={len(self.router.headers.raw_headers)}"
            )
        except Exception as e:  # noqa: BLE001
            out.append("[bg-read] RAISED " + fmt(e))
        await asyncio.sleep(0.05)
        async with self:
            self.log.extend(out)


class SubS(RootS):
    """A substate that inherits the router from RootS."""

    sub_ticks: int = 0
    sub_log: list[str] = []

    # ---- (b) same shapes from a substate ----
    @rx.event(background=True)
    async def bg_sub(self):
        """Background handler on a substate."""
        results: list[str] = []
        try:
            self.sub_ticks = 1
            results.append("[bg-sub] OUTSIDE direct field write ALLOWED (!)")
        except Exception as e:  # noqa: BLE001
            results.append("[bg-sub] OUTSIDE direct field write " + fmt(e))
        try:
            self.router.page.params["sub"] = "outside"
            results.append("[bg-sub] OUTSIDE router params write ALLOWED (!)")
        except Exception as e:  # noqa: BLE001
            results.append("[bg-sub] OUTSIDE router params write " + fmt(e))
        try:
            self.router.headers.raw_headers["x-sub"] = "outside"
            results.append("[bg-sub] OUTSIDE raw_headers write ALLOWED (!)")
        except Exception as e:  # noqa: BLE001
            results.append("[bg-sub] OUTSIDE raw_headers write " + fmt(e))

        async with self:
            try:
                self.router.page.params["sub"] = "inside"
                results.append(
                    f"[bg-sub] INSIDE router params write OK -> "
                    f"{dict(self.router.page.params)!r}"
                )
            except Exception as e:  # noqa: BLE001
                results.append("[bg-sub] INSIDE router params write RAISED " + fmt(e))
            root_dirty = sorted(self.parent_state.dirty_vars) if self.parent_state else []
            results.append(f"[bg-sub] INSIDE parent dirty_vars={root_dirty}")
            self.sub_ticks += 1
            n_before = len(self.log)
            self.log.extend(results)
            results.append(
                f"[bg-sub] root log extend from substate: len {n_before} -> {len(self.log)}"
            )
            self.sub_log.extend(results)

    @rx.event
    def sub_plain(self):
        """Plain substate handler reading and writing the router."""
        try:
            self.router.page.params["subplain"] = "yes"
            self.log.append(
                f"[sub-plain] write OK -> {dict(self.router.page.params)!r}"
            )
        except Exception as e:  # noqa: BLE001
            self.log.append("[sub-plain] write RAISED " + fmt(e))

    @rx.event(background=True)
    async def bg_nested_ctx(self):
        """Re-acquire the lock through a captured router container."""
        out: list[str] = []
        async with self:
            params = self.router.page.params
        try:
            async with params:
                params["nested"] = "1"
                out.append(f"[bg-nested] `async with params` OK -> {dict(params)!r}")
        except Exception as e:  # noqa: BLE001
            out.append("[bg-nested] `async with params` RAISED " + fmt(e))
        try:
            params["late"] = "1"
            out.append("[bg-nested] post-context write ALLOWED (!)")
        except Exception as e:  # noqa: BLE001
            out.append("[bg-nested] post-context write " + fmt(e))
        token = self.router.session.client_token
        ro = await rx.get_state(token, RootS)
        ro_params = ro.router.page.params
        try:
            async with ro_params:
                out.append("[bg-nested] READONLY `async with params` ALLOWED (!)")
        except Exception as e:  # noqa: BLE001
            out.append("[bg-nested] READONLY `async with params` " + fmt(e))
        async with self:
            self.sub_log.extend(out)


def index() -> rx.Component:
    """The single page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("#7230 router mutation guards"),
        rx.text(RootS.route_view, id="routeview"),
        rx.text(RootS.onload_note, id="onload"),
        rx.text(RootS.ticks.to_string(), id="ticks"),
        rx.text(SubS.sub_ticks.to_string(), id="subticks"),
        rx.hstack(
            rx.button("plain", id="plain", on_click=RootS.plain_rw),
            rx.button("bgroot", id="bgroot", on_click=RootS.bg_root),
            rx.button("bgsub", id="bgsub", on_click=SubS.bg_sub),
            rx.button("subplain", id="subplain", on_click=SubS.sub_plain),
            rx.button("bgread", id="bgread", on_click=RootS.bg_reads),
            rx.button("bgnested", id="bgnested", on_click=SubS.bg_nested_ctx),
            rx.button("clear", id="clear", on_click=RootS.clear),
        ),
        rx.box(
            rx.foreach(RootS.log, lambda line: rx.text(line, class_name="logline")),
            rx.foreach(SubS.sub_log, lambda line: rx.text(line, class_name="logline")),
            id="log",
        ),
        rx.link("to /other?q=1", href="/other?q=1", id="tolink"),
    )


def other() -> rx.Component:
    """A navigation target with query params.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("other"),
        rx.text(RootS.route_view, id="routeview"),
        rx.text(RootS.onload_note, id="onload"),
        rx.box(
            rx.foreach(RootS.log, lambda line: rx.text(line, class_name="logline")),
            id="log",
        ),
        rx.link("back", href="/", id="backlink"),
    )


app = rx.App()
app.add_page(index, route="/", on_load=RootS.on_load_probe)
app.add_page(other, route="/other", on_load=RootS.on_load_probe)
