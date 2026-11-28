from reflex_base.components.app_wraps import collect_subtree_app_wraps
from reflex_components_core.core.banner import (
    ConnectionBanner,
    ConnectionModal,
    ConnectionPulser,
    ConnectionToaster,
    WebsocketTargetURL,
    WifiOffPulse,
)
from reflex_components_radix.themes.typography.text import Text


def test_websocket_target_url():
    url = WebsocketTargetURL.create()
    var_data = url._get_all_var_data()
    assert var_data is not None
    assert sorted(key for key, _ in var_data.imports) == sorted((
        "$/utils/state",
        "$/env.json",
    ))


def test_connection_banner():
    banner = ConnectionBanner.create()
    imports = banner._get_all_imports(collapse=True)
    assert sorted(imports) == sorted((
        "react",
        "$/utils/context",
        "$/utils/state",
        "$/env.json",
    ))

    msg = "Connection error"
    custom_banner = ConnectionBanner.create(Text.create(msg))
    assert msg in str(custom_banner.render())


def test_connection_modal():
    modal = ConnectionModal.create()
    imports = modal._get_all_imports(collapse=True)
    assert sorted(imports) == sorted((
        "react",
        "$/utils/context",
        "$/utils/state",
        "$/env.json",
    ))

    msg = "Connection error"
    custom_modal = ConnectionModal.create(Text.create(msg))
    assert msg in str(custom_modal.render())


def test_connection_pulser():
    pulser = ConnectionPulser.create()
    _custom_code = pulser._get_all_custom_code()
    _imports = pulser._get_all_imports(collapse=True)


def test_connection_toaster_shows_hydration_errors_at_once():
    hooks = "\n".join(map(str, ConnectionToaster.create()._get_all_hooks()))
    hydration_check = hooks.index("error.code === 'hydration_payload_too_large'")

    # Checked before the two-error threshold, with an id no connection toast
    # dismisses, and kept open until the user closes it.
    assert hydration_check < hooks.index("(connectErrors.length >= 2)")
    assert 'id: "hydration-payload-error"' in hooks
    assert "duration: Infinity" in hooks


def test_connection_toaster_does_not_ask_for_the_toaster():
    """A connection error alone is no reason to bundle the toaster."""
    toaster = ConnectionToaster.create()
    hooks = toaster._get_all_hooks()

    # It shows through whichever toast function the app installed.
    assert list(hooks)[:2] == [
        "const connectErrors = useContext(EventLoopContext)[1];",
        "const toast = refs['__toast'];",
    ]
    assert collect_subtree_app_wraps(toaster) == {}


PULSER_CSS = (
    "@keyframes rx-connection-pulse{from{opacity:0}to{opacity:1}}"
    ".rx-connection-pulser{position:fixed;width:100vw;height:0}"
    ".rx-connection-pulse{color:crimson;z-index:9999;position:fixed;bottom:33px;"
    "right:33px;animation:rx-connection-pulse 1s infinite}"
)


def test_connection_pulser_is_styled_without_a_css_prop():
    """The indicator every app with state renders does not need Emotion."""
    pulser = ConnectionPulser.create()
    assert sorted(pulser._get_all_imports(collapse=True)) == [
        "$/utils/context",
        "$/utils/state",
        "lucide-react@1.26.0",
        "react",
    ]
    assert pulser.render() == {
        "name": '"div"',
        "props": [
            'className:"rx-connection-pulser"',
            (
                'title:("Connection Error: "+((connectErrors.length > 0) ? '
                "connectErrors[connectErrors.length - 1].message : ''))"
            ),
        ],
        "children": [
            {
                "name": '"style"',
                "props": [
                    'href:"rx-connection-pulser"',
                    'precedence:"reflex"',
                    "suppressHydrationWarning:true",
                ],
                "children": [{"contents": f'"{PULSER_CSS}"'}],
            },
            {
                "name": "Fragment",
                "props": [],
                "children": [
                    {
                        "cond_state": "(connectErrors.length > 0)",
                        "true_value": {
                            "name": "Fragment",
                            "props": [],
                            "children": [
                                {
                                    "name": "LucideWifiOff",
                                    "props": [
                                        'className:"rx-connection-pulse"',
                                        "size:32",
                                    ],
                                    "children": [],
                                }
                            ],
                        },
                        "false_value": {
                            "name": "Fragment",
                            "props": [],
                            "children": [],
                        },
                    }
                ],
            },
        ],
    }


def test_wifi_off_pulse_style_props_override_its_stylesheet():
    """A style given to the icon is a ``css`` prop over the class it keeps."""
    icon = WifiOffPulse.create(color="red", class_name="mine")
    assert icon.render() == {
        "name": "LucideWifiOff",
        "props": [
            'className:"rx-connection-pulse mine"',
            'css:({ ["color"] : "red" })',
            "size:32",
        ],
        "children": [],
    }
