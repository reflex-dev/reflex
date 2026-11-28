import pytest
from reflex_base.components.component import Component
from reflex_components_core.el.elements.media import Img, Source
from reflex_components_core.el.elements.metadata import Link
from reflex_components_core.el.elements.scripts import Script


@pytest.mark.parametrize(
    ("element", "props", "rendered_props"),
    [
        (
            Img,
            {"src": "/hero.webp", "fetch_priority": "high"},
            ['fetchPriority:"high"', 'src:"/hero.webp"'],
        ),
        (
            Link,
            {"rel": "preload", "href": "/font.woff2", "fetch_priority": "high"},
            ['fetchPriority:"high"', 'href:"/font.woff2"', 'rel:"preload"'],
        ),
        (
            Script,
            {"src": "/analytics.js", "fetch_priority": "low"},
            ['fetchPriority:"low"', 'src:"/analytics.js"'],
        ),
    ],
)
def test_fetch_priority(
    element: type[Component], props: dict[str, str], rendered_props: list[str]
):
    assert element.create(**props).render() == {
        "name": f'"{element.tag}"',
        "props": rendered_props,
        "children": [],
    }


def test_source_dimensions():
    source = Source.create(
        media="(min-width: 768px)", src_set="/wide.webp", width=1200, height=581
    )
    assert source.render() == {
        "name": '"source"',
        "props": [
            "height:581",
            'media:"(min-width: 768px)"',
            'srcSet:"/wide.webp"',
            "width:1200",
        ],
        "children": [],
    }


def test_img_dimensions_style_the_image():
    image = Img.create(src="/logo.png", width="5em", height="auto")
    assert str(image) == (
        'jsx("img",{css:({ ["width"] : "5em", ["height"] : "auto" }),src:"/logo.png"},)'
    )
