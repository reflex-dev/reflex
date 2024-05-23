import pytest

from reflex import constants
from reflex.app import App
from reflex.route import catchall_in_route, get_route_args, verify_route_validity


@pytest.mark.parametrize(
    "route_name, expected",
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
    "route_name,expected",
    [
        ("/events/[year]/[month]/[...slug]", "[...slug]"),
        ("pages/shop/[[...slug]]", "[[...slug]]"),
    ],
)
def test_catchall_in_route(route_name, expected):
    assert catchall_in_route(route_name) == expected


@pytest.mark.parametrize(
    "route_name",
    [
        "/products",
        "/products/[category]/[...]/details/[version]",
        "[...]",
        "/products/details",
    ],
)
def test_verify_valid_routes(route_name):
    verify_route_validity(route_name)


@pytest.mark.parametrize(
    "route_name",
    [
        "/products/[...]/details/[category]/latest",
        "/blog/[...]/post/[year]/latest",
        "/products/[...]/details/[...]/[category]/[...]/latest",
        "/products/[...]/details/category",
    ],
)
def test_verify_invalid_routes(route_name):
    with pytest.raises(ValueError):
        verify_route_validity(route_name)


@pytest.fixture()
def app():
    return App()


@pytest.mark.parametrize(
    "route1,route2",
    [
        ("/posts/[slug]", "/posts/[slug1]"),
        ("/posts/[slug]/info", "/posts/[slug1]/info1"),
        ("/posts/[slug]/info/[[slug1]]", "/posts/[slug1]/info1/[[slug2]]"),
        ("/posts/[slug]/info/[[slug1]]", "/posts/[slug]/info/[[slug2]]"),
        ("/posts/[slug]/info/[[...slug1]]", "/posts/[slug1]/info/[[...slug2]]"),
        ("/posts/[slug]/info/[[...slug1]]", "/posts/[slug]/info/[[...slug2]]"),
    ],
)
def test_check_routes_conflict_invalid(mocker, app, route1, route2):
    mocker.patch.object(app, "pages", {route1: []})
    with pytest.raises(ValueError):
        app._check_routes_conflict(route2)


@pytest.mark.parametrize(
    "route1,route2",
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
        ("/posts/[slug]/info/[[...slug1]]", "/posts/[slug]/info1/[[...slug1]]"),
        ("/posts/[slug]/info/[[...slug1]]", "/posts/[slug]/info1/[[...slug2]]"),
        ("/posts/[slug]/info/[...slug1]", "/posts/[slug]/info1/[...slug1]"),
        ("/posts/[slug]/info/[...slug1]", "/posts/[slug]/info1/[...slug2]"),
    ],
)
def test_check_routes_conflict_valid(mocker, app, route1, route2):
    mocker.patch.object(app, "pages", {route1: []})
    # test that running this does not throw an error.
    app._check_routes_conflict(route2)
