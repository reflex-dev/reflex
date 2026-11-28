"""Tests for the error boundary that wraps every app."""

from reflex_components_core.base.error_boundary import ErrorBoundary

import reflex as rx

# What the boundary renders in place of a page that failed to render.
FALLBACK = (
    '((event_args) => (jsx("div", ({className:"rx-error-boundary"}), (jsx("style", '
    '({href:"rx-error-boundary",precedence:"reflex",suppressHydrationWarning:true}), '
    '".rx-error-boundary{height:100%;width:100%;position:absolute;background-color:#fff;color:#000;display:flex;align-items:center;justify-content:center}.rx-error-boundary-content{display:flex;flex-direction:column;gap:0.5rem;max-width:min(80ch, '
    "90vw);border-radius:0.25rem;padding:1rem}.rx-error-boundary-heading{opacity:0.5;display:flex;gap:4vmin;align-items:center}.rx-error-boundary-title{font-size:5vmin;font-weight:bold}.rx-error-boundary-hint{opacity:0.75;margin-block:1rem}.rx-error-boundary-details{width:100%;background:color-mix(in "
    "srgb, currentColor 5%, "
    "transparent);max-height:15rem;overflow:auto;border-radius:0.4rem}.rx-error-boundary-details-body{padding:0.5rem}.rx-error-boundary-trace{word-break:break-word;white-space:pre-wrap}.rx-error-boundary-copy{padding:0.35rem "
    "1.35rem;margin-block:0.5rem;margin-inline-start:auto;background:color-mix(in "
    "srgb, currentColor 15%, "
    "transparent);border-radius:0.4rem;width:fit-content}.rx-error-boundary-copy:hover{background:color-mix(in "
    "srgb, currentColor 25%, "
    "transparent)}.rx-error-boundary-copy:active{background:color-mix(in srgb, "
    "currentColor 35%, "
    'transparent)}.rx-error-boundary-rule{border-color:currentColor;opacity:0.25}.rx-error-boundary-credit{display:flex;align-items:baseline;justify-content:center;font-family:monospace;--default-font-family:monospace;gap:0.5rem}.rx-error-boundary-logo{fill:currentColor}")), '
    '(jsx("div", ({className:"rx-error-boundary-content"}), (jsx("div", '
    '({className:"rx-error-boundary-heading"}), (jsx("svg", ({className:"lucide '
    "lucide-frown-icon "
    'lucide-frown",fill:"none",stroke:"currentColor",strokeLinecap:"round",strokeLinejoin:"round",strokeWidth:"2",viewBox:"0 '
    '0 24 24",width:"25vmin",xmlns:"http://www.w3.org/2000/svg"}), (jsx("circle", '
    '({cx:"12",cy:"12",r:"10"}))), (jsx("path", ({d:"M16 16s-1.5-2-4-2-4 2-4 2"}))), '
    '(jsx("line", ({x1:"9",x2:"9.01",y1:"9",y2:"9"}))), (jsx("line", '
    '({x1:"15",x2:"15.01",y1:"9",y2:"9"}))))), (jsx("h2", '
    '({className:"rx-error-boundary-title"}), "An error occurred while rendering this '
    'page.")))), (jsx("p", ({className:"rx-error-boundary-hint"}), "This is an error '
    'with the application itself. Refreshing the page might help.")), (jsx("div", '
    '({className:"rx-error-boundary-details"}), (jsx("div", '
    '({className:"rx-error-boundary-details-body"}), (jsx("pre", '
    "({className:\"rx-error-boundary-trace\"}), event_args.error.name + ': ' + "
    "event_args.error.message + '\\n' + event_args.error.stack)))))), "
    '(jsx("button", ({className:"rx-error-boundary-copy",onClick:((_e) => '
    '(addEvents([(ReflexEvent("_call_function", ({ ["function"] : (() => '
    '(navigator?.["clipboard"]?.["writeText"](event_args.error.name + \': \' + '
    "event_args.error.message + '\\n' + event_args.error.stack))), [\"callback\"] : "
    'null }), ({  })))], [_e], ({  }))))}), "Copy")), (jsx("hr", '
    '({className:"rx-error-boundary-rule"}))), (jsx(ReactRouterLink, '
    '({to:"https://reflex.dev"}), (jsx("div", '
    '({className:"rx-error-boundary-credit"}), "Built with ", (jsx("svg", '
    '({"aria-label":"Reflex",className:"rx-error-boundary-logo",height:"12",role:"img",width:"56",xmlns:"http://www.w3.org/2000/svg"}), '
    '(jsx("path", ({d:"M0 '
    "11.5999V0.399902H8.96V4.8799H6.72V2.6399H2.24V4.8799H6.72V7.1199H2.24V11.5999H0ZM6.72 "
    '11.5999V7.1199H8.96V11.5999H6.72Z"}))), (jsx("path", ({d:"M11.2 '
    '11.5999V0.399902H17.92V2.6399H13.44V4.8799H17.92V7.1199H13.44V9.3599H17.92V11.5999H11.2Z"}))), '
    '(jsx("path", ({d:"M20.16 '
    '11.5999V0.399902H26.88V2.6399H22.4V4.8799H26.88V7.1199H22.4V11.5999H20.16Z"}))), '
    '(jsx("path", ({d:"M29.12 '
    '11.5999V0.399902H31.36V9.3599H35.84V11.5999H29.12Z"}))), (jsx("path", '
    '({d:"M38.08 '
    '11.5999V0.399902H44.8V2.6399H40.32V4.8799H44.8V7.1199H40.32V9.3599H44.8V11.5999H38.08Z"}))), '
    '(jsx("path", ({d:"M47.04 4.8799V0.399902H49.28V4.8799H47.04ZM53.76 '
    "4.8799V0.399902H56V4.8799H53.76ZM49.28 7.1199V4.8799H53.76V7.1199H49.28ZM47.04 "
    '11.5999V7.1199H49.28V11.5999H47.04ZM53.76 11.5999V7.1199H56V11.5999H53.76Z"}))), '
    '(jsx("title", ({}), "Reflex")))))))))))))'
)


def test_default_fallback_is_styled_without_a_css_prop():
    """The boundary wraps every app: its fallback has no ``css`` prop."""
    boundary = ErrorBoundary.create(rx.el.div("page"))
    assert sorted(boundary._get_all_imports(collapse=True)) == [
        "$/utils/context",
        "$/utils/state",
        "@emotion/react",
        "react",
        "react-error-boundary@6.1.6",
        "react-router",
    ]
    fallback, _on_error = boundary.render()["props"]
    assert fallback == f"fallbackRender:{FALLBACK}"
