"""Routing & navigation test app for reflex 0.9.9a1 pre-release testing.

Covers:
- #6593 stale on_load cancellation on navigation + @rx.event
- #6790 [[...splat]] catchall prefix matching
- #6953 static/dynamic sibling routes (/articles/all/[x] + /articles/[id])
- #6919 chained events inherit routing data of the producing event
"""

import asyncio
import time

import reflex as rx

T0 = time.time()


def ts() -> str:
    """Seconds since app start, for ordering log entries.

    Returns:
        Elapsed time as a short string.
    """
    return f"{time.time() - T0:.1f}"


class VisitState(rx.State):
    """Records every on_load firing so tests can see which page's on_load ran."""

    visits: list[str] = []

    @rx.event
    def log_visit(self, page: str):
        """Record that a page's on_load fired.

        Args:
            page: Label of the page that loaded.
        """
        self.visits.append(f"{ts()}|{page}|path={self.router.url.path}")

    @rx.event
    def clear(self):
        """Clear the visit log."""
        self.visits = []


class SlowLoadState(rx.State):
    """Slow async on_load handler: appends progress steps ~1s apart."""

    progress: list[str] = []
    load_count: int = 0

    @rx.event
    async def slow_load(self):
        """The /slow page's on_load: 4 steps, 1s apart.

        Yields:
            Partial state updates after each step.
        """
        self.load_count += 1
        n = self.load_count
        self.progress.append(f"{ts()}|load{n}-start")
        yield
        for i in range(1, 5):
            await asyncio.sleep(1.0)
            self.progress.append(f"{ts()}|load{n}-step{i}")
            yield

    @rx.event
    def clear(self):
        """Clear progress log."""
        self.progress = []
        self.load_count = 0


class SlowBgState(rx.State):
    """Slow background-task on_load."""

    bg_progress: list[str] = []
    bg_count: int = 0

    @rx.event(background=True)
    async def slow_bg_load(self):
        """The /slowbg page's on_load as a background task: 4 steps, 1s apart."""
        async with self:
            self.bg_count += 1
            n = self.bg_count
            self.bg_progress.append(f"{ts()}|bg{n}-start")
        for i in range(1, 5):
            await asyncio.sleep(1.0)
            async with self:
                self.bg_progress.append(f"{ts()}|bg{n}-step{i}")

    @rx.event(background=True)
    async def slow_bg_click(self):
        """Background task started from a button click: 4 steps, 1s apart."""
        async with self:
            self.bg_progress.append(f"{ts()}|btnbg-start")
        for i in range(1, 5):
            await asyncio.sleep(1.0)
            async with self:
                self.bg_progress.append(f"{ts()}|btnbg-step{i}")

    @rx.event
    def clear(self):
        """Clear background progress log."""
        self.bg_progress = []
        self.bg_count = 0


class ClickState(rx.State):
    """supersedes=True on a normal button handler: rapid clicks, only latest wins."""

    started: int = 0
    results: list[str] = []
    normal_results: list[str] = []

    @rx.event
    async def slow_click(self):
        """Slow superseding click handler.

        Yields:
            Partial updates (start marker, then completion).
        """
        self.started += 1
        n = self.started
        yield
        await asyncio.sleep(1.5)
        self.results.append(f"{ts()}|click-{n}-done")
        yield

    @rx.event
    async def slow_click_normal(self):
        """Slow non-superseding click handler (baseline: all complete)."""
        await asyncio.sleep(0.7)
        self.normal_results.append(f"{ts()}|normal-done")

    @rx.event
    def clear(self):
        """Clear click logs."""
        self.started = 0
        self.results = []
        self.normal_results = []


class ChainState(rx.State):
    """Chained events must inherit routing data of the producing event (#6919)."""

    chain_log: list[str] = []

    @rx.event
    async def start_chain(self):
        """Click handler on /articles/[id]: sleeps then yields a chained event.

        Yields:
            The chained record_args event after a delay.
        """
        self.chain_log.append(f"{ts()}|start:path={self.router.url.path}:id={self.id}")
        yield
        await asyncio.sleep(2.0)
        yield ChainState.record_args("chained")

    @rx.event
    def record_args(self, tag: str):
        """Chained event: records routing data it resolves against.

        Args:
            tag: Marker of which invocation produced this record.
        """
        self.chain_log.append(
            f"{ts()}|record[{tag}]:path={self.router.url.path}:id={self.id}"
        )

    @rx.event
    def clear(self):
        """Clear chain log."""
        self.chain_log = []


def navbar() -> rx.Component:
    """Navigation links shared by all pages.

    Returns:
        The nav bar component.
    """
    return rx.hstack(
        rx.link("home", href="/", id="nav-home"),
        rx.link("slow", href="/slow", id="nav-slow"),
        rx.link("slowbg", href="/slowbg", id="nav-slowbg"),
        rx.link("other", href="/other", id="nav-other"),
        rx.link("posts-cat", href="/posts", id="nav-posts"),
        rx.link("postsomething", href="/postsomething", id="nav-postsomething"),
        rx.link("art-1", href="/articles/1", id="nav-art-1"),
        rx.link("art-2", href="/articles/2", id="nav-art-2"),
        rx.link("art-all-5", href="/articles/all/5", id="nav-art-all-5"),
        spacing="4",
    )


def status_footer() -> rx.Component:
    """Footer shown on every page exposing all state logs for assertions.

    Returns:
        The footer component.
    """
    return rx.vstack(
        rx.divider(),
        rx.text("slow progress:", weight="bold"),
        rx.box(SlowLoadState.progress.join(" ; "), id="slow-progress"),
        rx.text("bg progress:", weight="bold"),
        rx.box(SlowBgState.bg_progress.join(" ; "), id="bg-progress"),
        rx.text("visits:", weight="bold"),
        rx.box(VisitState.visits.join(" ; "), id="visits"),
        rx.text("chain log:", weight="bold"),
        rx.box(ChainState.chain_log.join(" ; "), id="chain-log"),
        align="start",
    )


def page_shell(*children: rx.Component) -> rx.Component:
    """Common page layout.

    Args:
        children: Page-specific content.

    Returns:
        The page component.
    """
    return rx.container(
        rx.vstack(navbar(), *children, status_footer(), align="start", spacing="4"),
        padding="2em",
    )


@rx.page(route="/", title="Home")
def index() -> rx.Component:
    """Home page with the supersedes-button test.

    Returns:
        The page component.
    """
    return page_shell(
        rx.heading("HOME", id="page-heading"),
        rx.hstack(
            rx.button("slow click (supersedes)", on_click=ClickState.slow_click, id="btn-supersede"),
            rx.button("slow click (normal)", on_click=ClickState.slow_click_normal, id="btn-normal"),
            rx.button("clear clicks", on_click=ClickState.clear, id="btn-clear-clicks"),
        ),
        rx.text("started: ", ClickState.started, id="click-started"),
        rx.box("results: ", ClickState.results.join(" ; "), id="click-results"),
        rx.box("normal: ", ClickState.normal_results.join(" ; "), id="click-normal-results"),
    )


@rx.page(route="/slow", title="Slow", on_load=SlowLoadState.slow_load)
def slow() -> rx.Component:
    """Page with a slow async on_load.

    Returns:
        The page component.
    """
    return page_shell(
        rx.heading("SLOW", id="page-heading"),
        rx.button("clear slow", on_click=SlowLoadState.clear, id="btn-clear-slow"),
    )


@rx.page(route="/slowbg", title="SlowBG", on_load=SlowBgState.slow_bg_load)
def slowbg() -> rx.Component:
    """Page whose on_load is a background task.

    Returns:
        The page component.
    """
    return page_shell(
        rx.heading("SLOWBG", id="page-heading"),
        rx.hstack(
            rx.button("start bg (button)", on_click=SlowBgState.slow_bg_click, id="btn-bg-click"),
            rx.button("clear bg", on_click=SlowBgState.clear, id="btn-clear-bg"),
        ),
    )


@rx.page(route="/other", title="Other", on_load=VisitState.log_visit("other"))
def other() -> rx.Component:
    """Plain fast page used as a navigation target.

    Returns:
        The page component.
    """
    return page_shell(rx.heading("OTHER", id="page-heading"))


@rx.page(
    route="/posts/[[...splat]]",
    title="PostsCatchall",
    on_load=VisitState.log_visit("posts-catchall"),
)
def posts_catchall() -> rx.Component:
    """Optional catchall under /posts.

    Returns:
        The page component.
    """
    return page_shell(
        rx.heading("POSTS-CATCHALL", id="page-heading"),
        rx.text("splat=", rx.State.splat.join(","), id="splat-args"),
    )


@rx.page(
    route="/postsomething",
    title="PostSomething",
    on_load=VisitState.log_visit("postsomething"),
)
def postsomething() -> rx.Component:
    """Static page sharing a prefix string with /posts (#6790).

    Returns:
        The page component.
    """
    return page_shell(rx.heading("POSTSOMETHING", id="page-heading"))


@rx.page(
    route="/articles/all/[x]",
    title="ArticlesAll",
    on_load=VisitState.log_visit("articles-all"),
)
def articles_all() -> rx.Component:
    """Static 'all' segment aligned with /articles/[id] dynamic segment (#6953).

    Returns:
        The page component.
    """
    return page_shell(
        rx.heading("ARTICLES-ALL-STATIC", id="page-heading"),
        rx.text("x=", rx.State.x, id="x-arg"),
    )


@rx.page(
    route="/articles/[id]",
    title="ArticleDetail",
    on_load=VisitState.log_visit("articles-id"),
)
def article_detail() -> rx.Component:
    """Dynamic article page with the chained-event routing test (#6919).

    Returns:
        The page component.
    """
    return page_shell(
        rx.heading("ARTICLE-DYNAMIC", id="page-heading"),
        rx.text("id=", rx.State.id, id="id-arg"),
        rx.hstack(
            rx.button("start chain", on_click=ChainState.start_chain, id="btn-chain"),
            rx.button("clear chain", on_click=ChainState.clear, id="btn-clear-chain"),
        ),
    )


app = rx.App()
