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


def test_connection_modal_shares_dismiss_state_under_auto_memoize():
    from reflex_base.event import EventChain
    from reflex_base.plugins import CompileContext, CompilerHooks
    from reflex_components_core import el

    from reflex.app import UnevaluatedPage
    from reflex.compiler import compiler
    from reflex.compiler.plugins import default_page_plugins

    def page_default():
        return ConnectionModal.create()

    ctx = CompileContext(
        pages=[UnevaluatedPage(route="/page", component=page_default)],
        hooks=CompilerHooks(plugins=default_page_plugins(auto_memoize=True)),
    )
    with ctx:
        compiled = ctx.compile()
        memo_files, _ = compiler.compile_memo_components(
            tuple(ctx.auto_memo_components.values())
        )
    bare_tag, cond_tag = (tag for tag, _ in ctx.auto_memo_components)
    assert len(memo_files) == 2
    expected_page_code = f"""
import {{{bare_tag}}} from "$/utils/components/{bare_tag}"
import {{Fragment,useContext,useEffect,useState}} from "react"
import env from "$/env.json"
import {{getBackendURL,isTrue,pyAnd,pyOr}} from "$/utils/state"
import {{{cond_tag}}} from "$/utils/components/{cond_tag}"
import {{EventLoopContext}} from "$/utils/context"
import {{jsx}} from "@emotion/react"





function Component() {{
const connectErrors = useContext(EventLoopContext)[1];
const [modalDismissed, setModalDismissed] = useState(false);
useEffect(() => {{ if (!(pyOr(pyOr((connectErrors.length >= 2), () => (((connectErrors.length > 0) && (connectErrors[connectErrors.length - 1].code === 'storage_blocked')))), () => (connectErrors.some((error) => error.code === 'hydration_payload_too_large'))))) {{ setModalDismissed(false); }} }}, [connectErrors]);

  return (
    jsx(Fragment,{{}},jsx(Fragment,{{}},(pyAnd(pyOr(pyOr((connectErrors.length >= 2), () => (((connectErrors.length > 0) && (connectErrors[connectErrors.length - 1].code === 'storage_blocked')))), () => (connectErrors.some((error) => error.code === 'hydration_payload_too_large'))), () => (!(modalDismissed)))?(jsx(Fragment,{{}},jsx("dialog",{{css:({{ ["zIndex"] : 9999 }}),open:pyAnd(pyOr(pyOr((connectErrors.length >= 2), () => (((connectErrors.length > 0) && (connectErrors[connectErrors.length - 1].code === 'storage_blocked')))), () => (connectErrors.some((error) => error.code === 'hydration_payload_too_large'))), () => (!(modalDismissed)))}},jsx("h2",{{}},"Connection Error"),jsx("span",{{}},jsx(Fragment,{{}},jsx({cond_tag},{{}},jsx(Fragment,{{}},jsx({bare_tag},{{}},)),jsx(Fragment,{{}},"Cannot connect to server: ",jsx({bare_tag},{{}},),". Check if server is reachable at ",getBackendURL(env.EVENT).href)))),jsx("div",{{css:({{ ["marginTop"] : "0.75rem" }})}},jsx("button",{{onClick:() => setModalDismissed(true),type:"button"}},"Close"))))):(jsx(Fragment,{{}},)))),jsx("title",{{}}," | Page"),jsx("meta",{{content:"",property:"og:image"}},))
  )
}}
Component.displayName = "Component(/page)";

export default Component;
""".strip()
    assert (compiled["/page"].output_code or "").strip() == expected_page_code

    def _no_args() -> list[object]:
        return []

    def page_custom():
        return ConnectionModal.create(
            el.div(
                "Custom error",
                on_mount=EventChain.create(value=_no_args, args_spec=_no_args),
                on_unmount=EventChain.create(value=_no_args, args_spec=_no_args),
            )
        )

    custom_ctx = CompileContext(
        pages=[UnevaluatedPage(route="/page", component=page_custom)],
        hooks=CompilerHooks(plugins=default_page_plugins(auto_memoize=True)),
    )
    with custom_ctx:
        custom_compiled = custom_ctx.compile()
        custom_memo_files, _ = compiler.compile_memo_components(
            tuple(custom_ctx.auto_memo_components.values())
        )
    assert len(custom_memo_files) == 1
    custom_tag = next(iter(custom_ctx.auto_memo_components))[0]
    expected_custom_page_code = f"""
import {{{custom_tag}}} from "$/utils/components/{custom_tag}"
import {{Fragment,useContext,useEffect,useState}} from "react"
import {{EventLoopContext}} from "$/utils/context"
import {{isTrue,pyAnd,pyOr}} from "$/utils/state"
import {{jsx}} from "@emotion/react"





function Component() {{
const connectErrors = useContext(EventLoopContext)[1];
const [modalDismissed, setModalDismissed] = useState(false);
useEffect(() => {{ if (!(pyOr(pyOr((connectErrors.length >= 2), () => (((connectErrors.length > 0) && (connectErrors[connectErrors.length - 1].code === 'storage_blocked')))), () => (connectErrors.some((error) => error.code === 'hydration_payload_too_large'))))) {{ setModalDismissed(false); }} }}, [connectErrors]);

  return (
    jsx(Fragment,{{}},jsx(Fragment,{{}},(pyAnd(pyOr(pyOr((connectErrors.length >= 2), () => (((connectErrors.length > 0) && (connectErrors[connectErrors.length - 1].code === 'storage_blocked')))), () => (connectErrors.some((error) => error.code === 'hydration_payload_too_large'))), () => (!(modalDismissed)))?(jsx(Fragment,{{}},jsx("dialog",{{css:({{ ["zIndex"] : 9999 }}),open:pyAnd(pyOr(pyOr((connectErrors.length >= 2), () => (((connectErrors.length > 0) && (connectErrors[connectErrors.length - 1].code === 'storage_blocked')))), () => (connectErrors.some((error) => error.code === 'hydration_payload_too_large'))), () => (!(modalDismissed)))}},jsx("h2",{{}},"Connection Error"),jsx({custom_tag},{{}},"Custom error"),jsx("div",{{css:({{ ["marginTop"] : "0.75rem" }})}},jsx("button",{{onClick:() => setModalDismissed(true),type:"button"}},"Close"))))):(jsx(Fragment,{{}},)))),jsx("title",{{}}," | Page"),jsx("meta",{{content:"",property:"og:image"}},))
  )
}}
Component.displayName = "Component(/page)";

export default Component;
""".strip()
    assert (
        custom_compiled["/page"].output_code or ""
    ).strip() == expected_custom_page_code
    expected_custom_memo_code = f"""
import {{ReflexEvent,applyEventActions,isTrue,mergeSlotProps}} from "$/utils/state"
import {{Fragment,memo,useEffect}} from "react"
import {{addEvents}} from "$/utils/context"
import {{jsx}} from "@emotion/react"






export const {custom_tag} = /*#__PURE__*/ (() => {{
const {custom_tag} = memo(({{children, ...rest}}) => {{
{"    "}
                useEffect(() => {{
                    ((...args) => (addEvents([], args, ({{  }}))))()
                    return () => {{
                        ((...args) => (addEvents([], args, ({{  }}))))()
                    }}
                }}, []);
    return(
        jsx("div",{{...mergeSlotProps(rest, ({{  }}))}},children)
    )
}});
{custom_tag}.displayName = "Div";
return {custom_tag};
}})();
""".strip()
    assert custom_memo_files[0][1].strip() == expected_custom_memo_code
