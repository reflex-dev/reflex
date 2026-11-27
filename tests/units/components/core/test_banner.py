from reflex_components_core.core.banner import (
    ConnectionBanner,
    ConnectionModal,
    ConnectionPulser,
    ConnectionToaster,
    WebsocketTargetURL,
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


def test_connection_toaster_shows_storage_blocked_errors_at_once():
    hooks = [str(hook) for hook in ConnectionToaster.create()._get_all_hooks()]
    assert hooks == [
        "const connectErrors = useContext(EventLoopContext)[1];",
        "const toast = refs['__toast'];",
        (
            'const toast_props = ({ ["description"] : ("Check if server is reachable at "'
            '+getBackendURL(env.EVENT).href), ["closeButton"] : true, '
            '["duration"] : 120000, ["id"] : "websocket-error" });'
        ),
        "const [userDismissed, setUserDismissed] = useState(false);",
        "const [waitedForBackend, setWaitedForBackend] = useState(false);",
        """(useEffect(
() => {
    if (connectErrors.some((error) => error.code === 'hydration_payload_too_large')) {
        toast?.error(((connectErrors.length > 0) ? connectErrors[connectErrors.length - 1].message : ''), {id: "hydration-payload-error", closeButton: true, duration: Infinity});
    } else if (((connectErrors.length > 0) && (connectErrors[connectErrors.length - 1].code === 'storage_blocked'))) {
        toast?.dismiss("websocket-error");
        toast?.error(((connectErrors.length > 0) ? connectErrors[connectErrors.length - 1].message : ''), {id: "storage-blocked-error", closeButton: true, duration: Infinity});
    } else if ((connectErrors.length >= 2)) {
        toast?.dismiss("storage-blocked-error");
        if (!userDismissed) {
            toast?.error(("Cannot connect to server: "+((connectErrors.length > 0) ? connectErrors[connectErrors.length - 1].message : '')+"."), {...toast_props, onDismiss: () => setUserDismissed(true)},)
        }
    } else {
        toast?.dismiss("storage-blocked-error");
        toast?.dismiss("websocket-error");
        setUserDismissed(false);  // after reconnection reset dismissed state
    }
}
, [connectErrors, waitedForBackend]))""",
    ]


def test_connection_banner_and_modal_handle_storage_blocked_errors():
    expected_message = {
        "name": "Fragment",
        "props": [],
        "children": [
            {
                "cond_state": (
                    "pyOr(((connectErrors.length > 0) && (connectErrors[connectErrors.length - 1].code === 'storage_blocked')), "
                    "() => (connectErrors.some((error) => error.code === 'hydration_payload_too_large')))"
                ),
                "true_value": {
                    "name": "Fragment",
                    "props": [],
                    "children": [
                        {
                            "contents": "((connectErrors.length > 0) ? connectErrors[connectErrors.length - 1].message : '')"
                        }
                    ],
                },
                "false_value": {
                    "name": "Fragment",
                    "props": [],
                    "children": [
                        {"contents": '"Cannot connect to server: "'},
                        {
                            "contents": "((connectErrors.length > 0) ? connectErrors[connectErrors.length - 1].message : '')"
                        },
                        {"contents": '". Check if server is reachable at "'},
                        {"contents": "getBackendURL(env.EVENT).href"},
                    ],
                },
            }
        ],
    }

    assert ConnectionBanner.create().render() == {
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
                            "name": '"div"',
                            "props": [
                                'css:({ ["display"] : "flex", ["justifyContent"] : "center", ["backgroundColor"] : "crimson", ["width"] : "100vw", ["padding"] : "5px", ["position"] : "fixed" })'
                            ],
                            "children": [
                                {
                                    "name": '"span"',
                                    "props": [
                                        'css:({ ["color"] : "black", ["fontSize"] : "1.125rem" })'
                                    ],
                                    "children": [expected_message],
                                }
                            ],
                        }
                    ],
                },
                "false_value": {"name": "Fragment", "props": [], "children": []},
            }
        ],
    }
    modal = ConnectionModal.create()
    expected_modal_cond = (
        "pyAnd(pyOr(pyOr((connectErrors.length >= 2), "
        "() => (((connectErrors.length > 0) && (connectErrors[connectErrors.length - 1].code === 'storage_blocked')))), "
        "() => (connectErrors.some((error) => error.code === 'hydration_payload_too_large'))), "
        "() => (!(modalDismissed)))"
    )
    assert [str(hook) for hook in modal._get_all_hooks()] == [
        "const connectErrors = useContext(EventLoopContext)[1];",
        "const [modalDismissed, setModalDismissed] = useState(false);",
        (
            "useEffect(() => { if (!(pyOr(pyOr((connectErrors.length >= 2), "
            "() => (((connectErrors.length > 0) && (connectErrors[connectErrors.length - 1].code === 'storage_blocked')))), "
            "() => (connectErrors.some((error) => error.code === 'hydration_payload_too_large'))))) "
            "{ setModalDismissed(false); } }, [connectErrors]);"
        ),
    ]
    assert modal.render() == {
        "name": "Fragment",
        "props": [],
        "children": [
            {
                "cond_state": expected_modal_cond,
                "true_value": {
                    "name": "Fragment",
                    "props": [],
                    "children": [
                        {
                            "name": '"dialog"',
                            "props": [
                                'css:({ ["zIndex"] : 9999 })',
                                f"open:{expected_modal_cond}",
                            ],
                            "children": [
                                {
                                    "name": '"h2"',
                                    "props": [],
                                    "children": [{"contents": '"Connection Error"'}],
                                },
                                {
                                    "name": '"span"',
                                    "props": [],
                                    "children": [expected_message],
                                },
                                {
                                    "name": '"div"',
                                    "props": ['css:({ ["marginTop"] : "0.75rem" })'],
                                    "children": [
                                        {
                                            "name": '"button"',
                                            "props": [
                                                "onClick:() => setModalDismissed(true)",
                                                'type:"button"',
                                            ],
                                            "children": [{"contents": '"Close"'}],
                                        }
                                    ],
                                },
                            ],
                        }
                    ],
                },
                "false_value": {"name": "Fragment", "props": [], "children": []},
            }
        ],
    }
