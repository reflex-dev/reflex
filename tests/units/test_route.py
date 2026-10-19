import pytest
from pytest_mock import MockerFixture
from reflex_base import constants

import reflex as rx
from reflex.app import App
from reflex.route import get_route_args, get_router, verify_route_validity


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
