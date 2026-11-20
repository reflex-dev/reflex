import random
from collections.abc import Callable

import pytest
from pytest_mock import MockerFixture
from reflex_base import constants

import reflex as rx
from reflex.app import App
from reflex.route import (
    get_route_args,
    get_route_regex,
    get_router,
    replace_brackets_with_keywords,
    route_specificity,
    verify_route_validity,
)


@pytest.mark.parametrize(
    ("route_name", "expected"),
    [
        ("/users/[id]", {"id": constants.RouteArgType.SINGLE}),
        (
            "/posts/[postId]/comments/[commentId]",
            {
                "postId": constants.RouteArgType.SINGLE,
                "commentId": constants.RouteArgType.SINGLE,
            },
        ),
    ],
)
def test_route_args(route_name, expected):
    assert get_route_args(route_name) == expected


@pytest.mark.parametrize(
    "route_name",
    [
        "/products/[id]/[id]",
        "/posts/[postId]/comments/[postId]",
    ],
)
def test_invalid_route_args(route_name):
    with pytest.raises(ValueError):
        get_route_args(route_name)


@pytest.mark.parametrize(
    "route_name",
    [
        "/products",
        "/products/details",
    ],
)
def test_verify_valid_routes(route_name):
    verify_route_validity(route_name)


@pytest.mark.parametrize(
    "route_name",
    [
        "/products/[category]/[...]/details/[version]",
        "[...]",
        "/products/[...]/details/[category]/latest",
        "/blog/[...]/post/[year]/latest",
        "/products/[...]/details/[...]/[category]/[...]/latest",
        "/products/[...]/details/category",
    ],
)
def test_verify_invalid_routes(route_name):
    with pytest.raises(ValueError):
        verify_route_validity(route_name)


@pytest.fixture
def app():
    return App()


@pytest.mark.parametrize(
    ("route1", "route2"),
    [
        ("/posts/[slug]", "/posts/[slug1]"),
        ("/posts/[slug]/info", "/posts/[slug1]/info1"),
        ("/posts/[slug]/info/[[slug1]]", "/posts/[slug1]/info1/[[slug2]]"),
        ("/posts/[slug]/info/[[slug1]]", "/posts/[slug]/info/[[slug2]]"),
        ("/posts/[slug]/info/[[...splat]]", "/posts/[slug1]/info/[[...splat]]"),
    ],
)
def test_check_routes_conflict_invalid(
    mocker: MockerFixture, app: App, route1: str, route2: str
):
    mocker.patch.object(app, "_pages", {route1: []})
    with pytest.raises(ValueError):
        app._check_routes_conflict(route2)


@pytest.mark.parametrize(
    ("route1", "route2"),
    [
        ("/posts/[slug]", "/post/[slug1]"),
        ("/posts/[slug]", "/post/[slug]"),
        ("/posts/[slug]/info", "/posts/[slug]/info1"),
        ("/posts/[slug]/info/[[slug1]]", "/posts/[slug]/info1/[[slug1]]"),
        ("/posts/[slug]/info/[[slug1]]", "/posts/[slug]/info1/[[slug2]]"),
        (
            "/posts/[slug]/info/[slug2]/[[slug1]]",
            "/posts/[slug]/info1/[slug2]/[[slug1]]",
        ),
        (
            "/posts/[slug]/info/[slug1]/random1/[slug2]/x",
            "/posts/[slug]/info/[slug1]/random/[slug4]/x1",
        ),
        ("/posts/[slug]/info/[[...splat]]", "/posts/[slug]/info1/[[...splat]]"),
        ("/posts/[slug]/info/[...slug1]", "/posts/[slug]/info1/[...slug1]"),
        ("/posts/[slug]/info/[...slug1]", "/posts/[slug]/info1/[...slug2]"),
        # static siblings of dynamic segments are legal (static wins in React Router)
        ("/posts/[slug]", "/posts/all/[x]"),
        ("/posts/all/[x]", "/posts/[slug]"),
        ("/[org]/dashboard", "/admin/devices/[pk]"),
        ("/admin/devices/[pk]", "/[org]/dashboard"),
    ],
)
def test_check_routes_conflict_valid(mocker: MockerFixture, app, route1, route2):
    mocker.patch.object(app, "_pages", {route1: []})
    # test that running this does not throw an error.
    app._check_routes_conflict(route2)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/posts", "posts/[[...splat]]"),
        ("/posts/", "posts/[[...splat]]"),
        ("/posts/2024/hello", "posts/[[...splat]]"),
        ("/postsomething", None),
        ("/posts-archive", None),
    ],
)
def test_get_router_splat_catchall(path: str, expected: str | None):
    # The frontend maps [[...splat]] to React Router's `posts/*`, which matches
    # the route and its descendants but not paths that merely share the prefix.
    router = get_router(["posts/[[...splat]]"])
    assert router(path) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/About", "about"),
        ("/ABOUT/", "about"),
        ("/Posts/42", "posts/[id]"),
        ("/team", "Team"),
        ("/", "index"),
        # React Router folds ASCII case only.
        ("/k\u0131t", None),
        ("/K\u0130T", None),
        ("/\u212ait", None),
    ],
)
def test_get_router_ignores_case(path: str, expected: str | None):
    # React Router renders a page for any casing of its path, so the backend
    # must resolve the same route to run its on_load events.
    router = get_router(["index", "about", "posts/[id]", "Team", "kit"])
    assert router(path) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/apple", "apple"),
        ("/app", "app"),
        ("/", "index"),
    ],
)
def test_get_router_ignores_frontend_path(
    mocker: MockerFixture, path: str, expected: str | None
):
    # The frontend sends basename-relative paths, so a route that starts with the
    # frontend_path text must not have that text stripped again.
    conf = rx.Config(app_name="testing", frontend_path="/app")
    mocker.patch("reflex_base.config._get_config", return_value=conf)
    router = get_router(["index", "app", "apple"])
    assert router(path) == expected


@pytest.mark.parametrize(
    ("url_path", "expected"),
    [
        ("/app", ["index"]),
        ("/app/", ["index"]),
        ("/app/apple", ["apple"]),
        ("/app/app", ["app"]),
        ("/apple", ["404"]),
    ],
)
def test_get_load_events_strips_frontend_path(
    mocker: MockerFixture, url_path: str, expected: list[str]
):
    conf = rx.Config(app_name="testing", frontend_path="/app")
    mocker.patch("reflex_base.config._get_config", return_value=conf)
    app = App()
    app._unevaluated_pages = dict.fromkeys(["index", "app", "apple"])  # pyright: ignore[reportAttributeAccessIssue]
    app._load_events = {  # pyright: ignore[reportAttributeAccessIssue]
        "index": ["index"],
        "app": ["app"],
        "apple": ["apple"],
        "404": ["404"],
    }
    assert app.get_load_events(url_path) == expected


def _reference_router(routes: list[str]) -> Callable[[str], str | None]:
    """Match paths the way get_router did before its trie: a regex scan.

    Each route compiles to ``get_route_regex``; routes are tried in
    ``route_specificity`` order, ties in registration order, and the first
    match wins.

    Args:
        routes: The routes to match against.

    Returns:
        A function returning the route a path matches, or None.
    """
    keyworded = {replace_brackets_with_keywords(route): route for route in routes}
    ordered = sorted(keyworded.items(), key=lambda item: route_specificity(item[0]))
    regexes = [(get_route_regex(keyworded), route) for keyworded, route in ordered]

    def match(path: str) -> str | None:
        path = "/" + path.removeprefix("/").removesuffix("/")
        if path == "/index":
            path = "/"
        return next((route for regex, route in regexes if regex.fullmatch(path)), None)

    return match


ROUTE_POOL: tuple[str, ...] = (
    "index",
    "about",
    "About",
    "k-it",
    "posts",
    "posts/new",
    "posts/[id]",
    "posts/[slug]",
    "posts/[id]/edit",
    "posts/[[page]]",
    "posts/[[...splat]]",
    "[slug]",
    "[a]/b",
    "x/[c]",
    "x/b",
    "[[lang]]/about",
    "[[...splat]]",
    "docs/[[...splat]]",
    "docs/api/[[...splat]]",
    "docs/[section]/[[page]]",
    "shop/[[cat]]/[[sub]]",
    "a/[b]/[c]",
    "a/[[b]]/[[...splat]]",
)
SEGMENT_POOL: tuple[str, ...] = (
    "",
    "index",
    "INDEX",
    "about",
    "ABOUT",
    "k-it",
    "K-IT",
    "posts",
    "Posts",
    "new",
    "1",
    "edit",
    "x",
    "X",
    "b",
    "a",
    "docs",
    "api",
    "shop",
    "\N{KELVIN SIGN}it",  # lowercases to an ASCII k outside ASCII folding
    "\N{LATIN SMALL LETTER E WITH ACUTE}",
    "a\nb",
)


def test_get_router_matches_the_regex_scan():
    """The trie router picks the route the regex scan picked, for every path."""
    rng = random.Random(7878)
    mismatches = []
    for _ in range(400):
        routes = rng.sample(ROUTE_POOL, rng.randint(1, 10))
        router = get_router(routes)
        reference = _reference_router(routes)
        for _ in range(60):
            segments = rng.choices(SEGMENT_POOL, k=rng.randint(0, 4))
            path = rng.choice(("/", "", "//")) + "/".join(segments)
            path += rng.choice(("", "", "/", "//"))
            if (expected := reference(path)) != (actual := router(path)):
                mismatches.append((routes, path, expected, actual))
    assert mismatches == []


@pytest.mark.parametrize(
    ("routes", "expected"),
    [
        (["[a]/b", "x/[c]"], "[a]/b"),
        (["x/[c]", "[a]/b"], "x/[c]"),
        (["x/[c]", "[a]/b", "x/b"], "x/b"),
        (["posts/[[...splat]]", "[slug]/[id]"], "[slug]/[id]"),
    ],
)
def test_get_router_ranks_by_dynamic_segment_counts(routes: list[str], expected: str):
    """Fewer catch-all, optional, then single segments win; ties go to the first.

    Args:
        routes: The routes, in registration order.
        expected: The route ``/x/b`` or ``/posts/b`` resolves to.
    """
    path = "/posts/b" if "posts/[[...splat]]" in routes else "/x/b"
    assert get_router(routes)(path) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/docs", "docs/[[...splat]]"),
        ("/docs/a/b", "docs/[[...splat]]"),
        ("/docs/a\nb", None),
        ("/posts/", None),
        ("/posts//", "posts/[id]"),
        ("/posts///", "posts/[id]"),
        ("/posts/1/", "posts/[id]"),
    ],
)
def test_get_router_segment_edge_cases(path: str, expected: str | None):
    """A single segment may be empty and a catch-all stops at a newline.

    One trailing slash is stripped before matching and a route allows one more,
    so ``/posts/`` has no segment for ``[id]`` while ``/posts//`` and
    ``/posts///`` give it an empty one.

    Args:
        path: The path to match.
        expected: The route it resolves to.
    """
    assert get_router(["docs/[[...splat]]", "posts/[id]"])(path) == expected


def test_get_router_rejects_catchall_before_the_last_segment():
    """A catch-all that is not the last segment cannot be matched by segment."""
    with pytest.raises(
        ValueError,
        match=r"^Catchall pattern `\[\[\.\.\.splat\]\]` must be at the end of the route\.$",
    ):
        get_router(["docs/[[...splat]]/edit"])
