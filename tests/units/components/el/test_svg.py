from collections.abc import Callable

import pytest
from reflex_base.components.component import Component
from reflex_components_core.el.elements.media import (
    Animate,
    AnimateMotion,
    AnimateTransform,
    Circle,
    ClipPath,
    Defs,
    Ellipse,
    FeDropShadow,
    FeMerge,
    FeMergeNode,
    Filter,
    ForeignObject,
    G,
    Line,
    LinearGradient,
    Marker,
    Mask,
    Path,
    Pattern,
    Polygon,
    Polyline,
    RadialGradient,
    Rect,
    Set,
    Stop,
    Svg,
    SvgA,
    SvgImage,
    SvgPresentationProps,
    Switch,
    Symbol,
    Text,
    TextPath,
    TSpan,
    Use,
    svg,
)


def test_circle():
    circle = Circle.create().render()
    assert circle["name"] == '"circle"'


def test_defs():
    defs = Defs.create().render()
    assert defs["name"] == '"defs"'


def test_ellipse():
    ellipse = Ellipse.create().render()
    assert ellipse["name"] == '"ellipse"'


def test_line():
    line = Line.create().render()
    assert line["name"] == '"line"'


def test_linear_gradient():
    linear_gradient = LinearGradient.create().render()
    assert linear_gradient["name"] == '"linearGradient"'


def test_path():
    path = Path.create().render()
    assert path["name"] == '"path"'


def test_polygon():
    polygon = Polygon.create().render()
    assert polygon["name"] == '"polygon"'


def test_radial_gradient():
    radial_gradient = RadialGradient.create().render()
    assert radial_gradient["name"] == '"radialGradient"'


def test_rect():
    rect = Rect.create().render()
    assert rect["name"] == '"rect"'


def test_svg():
    svg = Svg.create().render()
    assert svg["name"] == '"svg"'


def test_text():
    text = Text.create().render()
    assert text["name"] == '"text"'


def test_stop():
    stop = Stop.create().render()
    assert stop["name"] == '"stop"'


def test_marker():
    marker = Marker.create().render()
    assert marker["name"] == '"marker"'


def test_g():
    g = G.create().render()
    assert g["name"] == '"g"'


def test_presentation_props_render_as_attributes():
    path = Path.create(
        clip_path="url(#clip)",
        clip_rule="evenodd",
        d="M0 0h10",
        direction="rtl",
        dominant_baseline="middle",
        fill="none",
        fill_opacity=0.5,
        fill_rule="evenodd",
        filter="url(#shadow)",
        font_family="serif",
        font_size=12,
        font_style="italic",
        font_weight=700,
        letter_spacing=1,
        marker_end="url(#end)",
        marker_mid="url(#mid)",
        marker_start="url(#start)",
        mask="url(#mask)",
        opacity=0.9,
        stroke="currentColor",
        stroke_dasharray="4 2",
        stroke_dashoffset=1,
        stroke_linecap="round",
        stroke_linejoin="bevel",
        stroke_miterlimit=4,
        stroke_opacity=0.8,
        stroke_width=1.5,
        text_anchor="middle",
        transform="translate(1 2)",
    ).render()
    assert path == {
        "name": '"path"',
        "props": [
            'clipPath:"url(#clip)"',
            'clipRule:"evenodd"',
            'd:"M0 0h10"',
            'direction:"rtl"',
            'dominantBaseline:"middle"',
            'fill:"none"',
            "fillOpacity:0.5",
            'fillRule:"evenodd"',
            'filter:"url(#shadow)"',
            'fontFamily:"serif"',
            "fontSize:12",
            'fontStyle:"italic"',
            "fontWeight:700",
            "letterSpacing:1",
            'markerEnd:"url(#end)"',
            'markerMid:"url(#mid)"',
            'markerStart:"url(#start)"',
            'mask:"url(#mask)"',
            "opacity:0.9",
            'stroke:"currentColor"',
            'strokeDasharray:"4 2"',
            "strokeDashoffset:1",
            'strokeLinecap:"round"',
            'strokeLinejoin:"bevel"',
            "strokeMiterlimit:4",
            "strokeOpacity:0.8",
            "strokeWidth:1.5",
            'textAnchor:"middle"',
            'transform:"translate(1 2)"',
        ],
        "children": [],
    }


@pytest.mark.parametrize(
    "element",
    [
        Circle,
        ClipPath,
        Ellipse,
        ForeignObject,
        G,
        Line,
        Marker,
        Mask,
        Path,
        Pattern,
        Polygon,
        Polyline,
        Rect,
        Svg,
        SvgA,
        SvgImage,
        Switch,
        Symbol,
        Text,
        TextPath,
        TSpan,
        Use,
    ],
)
def test_presentation_props(element: type[SvgPresentationProps]):
    rendered = element.create(
        fill="none", opacity=0.5, stroke_width=2, transform="scale(2)"
    ).render()
    assert rendered == {
        "name": f'"{element.tag}"',
        "props": [
            'fill:"none"',
            "opacity:0.5",
            "strokeWidth:2",
            'transform:"scale(2)"',
        ],
        "children": [],
    }


@pytest.mark.parametrize(
    ("element", "props", "rendered_props"),
    [
        (
            Animate,
            {"attribute_name": "opacity", "fill": "freeze"},
            ['attributeName:"opacity"', 'fill:"freeze"'],
        ),
        (
            AnimateMotion,
            {"calc_mode": "linear", "fill": "freeze"},
            ['calcMode:"linear"', 'fill:"freeze"'],
        ),
        (
            AnimateTransform,
            {"calc_mode": "discrete", "fill": "remove"},
            ['calcMode:"discrete"', 'fill:"remove"'],
        ),
        (Set, {"to": "1", "fill": "freeze"}, ['fill:"freeze"', 'to:"1"']),
    ],
)
def test_animation_fill(
    element: type[Component], props: dict[str, str], rendered_props: list[str]
):
    assert element.create(**props).render() == {
        "name": f'"{element.tag}"',
        "props": rendered_props,
        "children": [],
    }


def test_filter():
    shadow = Filter.create(
        FeDropShadow.create(
            dx=0,
            dy=2,
            std_deviation=3,
            flood_color="#000",
            flood_opacity=0.2,
            result="shadow",
        ),
        FeMerge.create(
            FeMergeNode.create(in_="shadow"),
            FeMergeNode.create(in_="SourceGraphic"),
        ),
        x="-10%",
        y="-20%",
        width="120%",
        height="150%",
        filter_units="objectBoundingBox",
        color_interpolation_filters="sRGB",
    )
    assert str(shadow) == (
        'jsx("filter",{colorInterpolationFilters:"sRGB",filterUnits:"objectBoundingBox",'
        'height:"150%",width:"120%",x:"-10%",y:"-20%"},'
        'jsx("feDropShadow",{dx:0,dy:2,floodColor:"#000",floodOpacity:0.2,'
        'result:"shadow",stdDeviation:3},),'
        'jsx("feMerge",{},jsx("feMergeNode",{in:"shadow"},),'
        'jsx("feMergeNode",{in:"SourceGraphic"},)))'
    )


@pytest.mark.parametrize(
    ("create", "props", "expected"),
    [
        (svg.filter, {}, ("filter", [])),
        (
            svg.fe_blend,
            {"in_": "SourceGraphic", "in2": "BackgroundImage", "mode": "multiply"},
            (
                "feBlend",
                ['in:"SourceGraphic"', 'in2:"BackgroundImage"', 'mode:"multiply"'],
            ),
        ),
        (
            svg.fe_color_matrix,
            {"type": "saturate", "values": 0.5},
            ("feColorMatrix", ['type:"saturate"', "values:0.5"]),
        ),
        (svg.fe_component_transfer, {"in_": "a"}, ("feComponentTransfer", ['in:"a"'])),
        (
            svg.fe_composite,
            {"operator": "arithmetic", "k1": 0, "k2": 1, "k3": 1, "k4": 0},
            ("feComposite", ["k1:0", "k2:1", "k3:1", "k4:0", 'operator:"arithmetic"']),
        ),
        (
            svg.fe_convolve_matrix,
            {
                "order": 3,
                "kernel_matrix": "0 1 0 1 -4 1 0 1 0",
                "divisor": 1,
                "bias": 0,
                "target_x": 1,
                "target_y": 1,
                "edge_mode": "none",
                "kernel_unit_length": 2,
                "preserve_alpha": True,
            },
            (
                "feConvolveMatrix",
                [
                    "bias:0",
                    "divisor:1",
                    'edgeMode:"none"',
                    'kernelMatrix:"0 1 0 1 -4 1 0 1 0"',
                    "kernelUnitLength:2",
                    "order:3",
                    "preserveAlpha:true",
                    "targetX:1",
                    "targetY:1",
                ],
            ),
        ),
        (
            svg.fe_diffuse_lighting,
            {"surface_scale": 2, "diffuse_constant": 1, "lighting_color": "white"},
            (
                "feDiffuseLighting",
                ["diffuseConstant:1", 'lightingColor:"white"', "surfaceScale:2"],
            ),
        ),
        (
            svg.fe_displacement_map,
            {"scale": 20, "x_channel_selector": "R", "y_channel_selector": "G"},
            (
                "feDisplacementMap",
                ["scale:20", 'xChannelSelector:"R"', 'yChannelSelector:"G"'],
            ),
        ),
        (
            svg.fe_distant_light,
            {"azimuth": 45, "elevation": 30},
            ("feDistantLight", ["azimuth:45", "elevation:30"]),
        ),
        (svg.fe_drop_shadow, {"in_": "a"}, ("feDropShadow", ['in:"a"'])),
        (
            svg.fe_flood,
            {"flood_color": "red", "flood_opacity": 0.5},
            ("feFlood", ['floodColor:"red"', "floodOpacity:0.5"]),
        ),
        (
            svg.fe_func_a,
            {"type": "table", "table_values": "0 1"},
            ("feFuncA", ['tableValues:"0 1"', 'type:"table"']),
        ),
        (
            svg.fe_func_b,
            {"type": "linear", "slope": 2, "intercept": 0},
            ("feFuncB", ["intercept:0", "slope:2", 'type:"linear"']),
        ),
        (
            svg.fe_func_g,
            {"type": "gamma", "amplitude": 1, "exponent": 2, "offset": 0},
            ("feFuncG", ["amplitude:1", "exponent:2", "offset:0", 'type:"gamma"']),
        ),
        (svg.fe_func_r, {"type": "identity"}, ("feFuncR", ['type:"identity"'])),
        (
            svg.fe_gaussian_blur,
            {"std_deviation": "2 4", "edge_mode": "duplicate"},
            ("feGaussianBlur", ['edgeMode:"duplicate"', 'stdDeviation:"2 4"']),
        ),
        (
            svg.fe_image,
            {
                "href": "/a.png",
                "preserve_aspect_ratio": "none",
                "cross_origin": "anonymous",
            },
            (
                "feImage",
                [
                    'crossOrigin:"anonymous"',
                    'href:"/a.png"',
                    'preserveAspectRatio:"none"',
                ],
            ),
        ),
        (svg.fe_merge, {"result": "merged"}, ("feMerge", ['result:"merged"'])),
        (svg.fe_merge_node, {"in_": "a"}, ("feMergeNode", ['in:"a"'])),
        (
            svg.fe_morphology,
            {"operator": "dilate", "radius": 2},
            ("feMorphology", ['operator:"dilate"', "radius:2"]),
        ),
        (
            svg.fe_offset,
            {"dx": 2, "dy": 3},
            ("feOffset", ["dx:2", "dy:3"]),
        ),
        (
            svg.fe_point_light,
            {"x": 1, "y": 2, "z": 3},
            ("fePointLight", ["x:1", "y:2", "z:3"]),
        ),
        (
            svg.fe_specular_lighting,
            {"specular_constant": 1, "specular_exponent": 20},
            ("feSpecularLighting", ["specularConstant:1", "specularExponent:20"]),
        ),
        (
            svg.fe_spot_light,
            {
                "points_at_x": 1,
                "points_at_y": 2,
                "points_at_z": 3,
                "limiting_cone_angle": 30,
            },
            (
                "feSpotLight",
                ["limitingConeAngle:30", "pointsAtX:1", "pointsAtY:2", "pointsAtZ:3"],
            ),
        ),
        (
            svg.fe_tile,
            {"x": 0, "y": 0, "width": 10, "height": 10},
            ("feTile", ["height:10", "width:10", "x:0", "y:0"]),
        ),
        (
            svg.fe_turbulence,
            {
                "base_frequency": "0.05",
                "num_octaves": 2,
                "seed": 3,
                "stitch_tiles": "stitch",
                "type": "fractalNoise",
            },
            (
                "feTurbulence",
                [
                    'baseFrequency:"0.05"',
                    "numOctaves:2",
                    "seed:3",
                    'stitchTiles:"stitch"',
                    'type:"fractalNoise"',
                ],
            ),
        ),
    ],
)
def test_filter_elements(
    create: Callable[..., Component],
    props: dict[str, object],
    expected: tuple[str, list[str]],
):
    tag, rendered_props = expected
    assert create(**props).render() == {
        "name": f'"{tag}"',
        "props": rendered_props,
        "children": [],
    }
