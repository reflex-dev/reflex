import pytest

from nextpy import constants
from nextpy.core.route import catchall_in_route, get_route_args, verify_route_validity


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
