import { createHotContext as __vite__createHotContext } from "/@vite/client";import.meta.hot = __vite__createHotContext("/app/routes/_index.jsx");const _c = __vite__cjsImport3_react_compilerRuntime["c"];const Fragment = __vite__cjsImport8_react["Fragment"]; const useEffect = __vite__cjsImport8_react["useEffect"];import RefreshRuntime from "/@id/__x00__virtual:react-router/hmr-runtime";const inWebWorker = typeof WorkerGlobalScope !== 'undefined' && self instanceof WorkerGlobalScope;let prevRefreshReg;let prevRefreshSig;if (import.meta.hot && !inWebWorker) {  if (!window.__vite_plugin_react_preamble_installed__) {    throw new Error(      "React Router Vite plugin can't detect preamble. Something is wrong."    );  }  prevRefreshReg = window.$RefreshReg$;  prevRefreshSig = window.$RefreshSig$;  window.$RefreshReg$ = (type, id) => {    RefreshRuntime.register(type, "/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_cm/refsrepro_patch/.web/app/routes/_index.jsx" + " " + id)  };  window.$RefreshSig$ = RefreshRuntime.createSignatureFunctionForTransform;}var _s = $RefreshSig$();
import { UNSAFE_withComponentProps as _UNSAFE_withComponentProps } from "/node_modules/.vite/deps/react-router.js?v=b9c2de7b";
import __vite__cjsImport3_react_compilerRuntime from "/node_modules/.vite/deps/react_compiler-runtime.js?v=b9c2de7b";
import { ReflexEvent, applyEventActions, refs, useRegisteredRef } from "/utils/state.js";
import { Button as RadixThemesButton, Flex as RadixThemesFlex, Heading as RadixThemesHeading, Text as RadixThemesText, TextField as RadixThemesTextField } from "/node_modules/.vite/deps/@radix-ui_themes.js?v=a9662ffb";
import { addEvents } from "/utils/context.jsx";
import { useStateContext } from "/utils/context-registry.js";
import __vite__cjsImport8_react from "/node_modules/.vite/deps/react.js?v=b9c2de7b";
import { jsx } from "/node_modules/.vite/deps/@emotion_react.js?v=86f892c5";
function Component() {
  _s();
  const $ = _c(28);
  if ($[0] !== "aabd838d0396c0fbb25191eccb505723d88c44631e97f3981ea0145526b5b1bc") {
    for (let $i = 0; $i < 28; $i += 1) {
      $[$i] = Symbol.for("react.memo_cache_sentinel");
    }
    $[0] = "aabd838d0396c0fbb25191eccb505723d88c44631e97f3981ea0145526b5b1bc";
  }
  const ref_h = useRegisteredRef("ref_h");
  const ref_target = useRegisteredRef("ref_target");
  const ref_raw = useRegisteredRef("ref_raw");
  const ref_callfn = useRegisteredRef("ref_callfn");
  const reflex___state____state__refsrepro___refsrepro___s = useStateContext("reflex___state____state.refsrepro___refsrepro___s");
  const ref_log = useRegisteredRef("ref_log");
  let t0;
  if ($[1] === Symbol.for("react.memo_cache_sentinel")) {
    t0 = {};
    $[1] = t0;
  } else {
    t0 = $[1];
  }
  let t1;
  if ($[2] === Symbol.for("react.memo_cache_sentinel")) {
    t1 = {
      align: "start",
      className: "rx-Stack",
      direction: "column",
      gap: "3"
    };
    $[2] = t1;
  } else {
    t1 = $[2];
  }
  let t2;
  if ($[3] !== ref_h) {
    t2 = jsx(RadixThemesHeading, {
      id: "h",
      ref: ref_h
    }, "refs repro");
    $[3] = ref_h;
    $[4] = t2;
  } else {
    t2 = $[4];
  }
  let t3;
  if ($[5] !== ref_target) {
    t3 = jsx(RadixThemesTextField.Root, {
      id: "target",
      ref: ref_target
    });
    $[5] = ref_target;
    $[6] = t3;
  } else {
    t3 = $[6];
  }
  let t4;
  if ($[7] === Symbol.for("react.memo_cache_sentinel")) {
    t4 = _e => ((...t5) => {
      const args = t5;
      return (() => {
        refs.ref_target.current.value = "set by raw var";
      })({
        "button": _e?.button,
        "buttons": _e?.buttons,
        "client_x": _e?.clientX,
        "client_y": _e?.clientY,
        "alt_key": _e?.altKey,
        "ctrl_key": _e?.ctrlKey,
        "meta_key": _e?.metaKey,
        "shift_key": _e?.shiftKey
      }, ...args);
    })(_e);
    $[7] = t4;
  } else {
    t4 = $[7];
  }
  let t5;
  if ($[8] !== ref_raw) {
    t5 = jsx(RadixThemesButton, {
      id: "raw",
      onClick: t4,
      ref: ref_raw
    }, "raw var handler");
    $[8] = ref_raw;
    $[9] = t5;
  } else {
    t5 = $[9];
  }
  let t6;
  if ($[10] === Symbol.for("react.memo_cache_sentinel")) {
    t6 = _e_0 => addEvents([ReflexEvent("_call_function", {
      "function": () => refs.ref_target.current.value,
      "callback": "(_result) => {addEvents([ReflexEvent(\"reflex___state____state.refsrepro___refsrepro___s.set_log\", {v:_result})])}"
    }, {})], [_e_0], {});
    $[10] = t6;
  } else {
    t6 = $[10];
  }
  let t7;
  if ($[11] !== ref_callfn) {
    t7 = jsx(RadixThemesButton, {
      id: "callfn",
      onClick: t6,
      ref: ref_callfn
    }, "call_function");
    $[11] = ref_callfn;
    $[12] = t7;
  } else {
    t7 = $[12];
  }
  let t8;
  if ($[13] !== ref_log) {
    t8 = {
      as: "p",
      id: "log",
      ref: ref_log
    };
    $[13] = ref_log;
    $[14] = t8;
  } else {
    t8 = $[14];
  }
  let t9;
  if ($[15] !== reflex___state____state__refsrepro___refsrepro___s.log_rx_state_ || $[16] !== t8) {
    t9 = jsx(RadixThemesText, t8, "log: ", reflex___state____state__refsrepro___refsrepro___s.log_rx_state_);
    $[15] = reflex___state____state__refsrepro___refsrepro___s.log_rx_state_;
    $[16] = t8;
    $[17] = t9;
  } else {
    t9 = $[17];
  }
  let t10;
  if ($[18] !== t2 || $[19] !== t3 || $[20] !== t5 || $[21] !== t7 || $[22] !== t9) {
    t10 = jsx(RadixThemesFlex, t1, t2, t3, t5, t7, t9);
    $[18] = t2;
    $[19] = t3;
    $[20] = t5;
    $[21] = t7;
    $[22] = t9;
    $[23] = t10;
  } else {
    t10 = $[23];
  }
  let t11;
  if ($[24] === Symbol.for("react.memo_cache_sentinel")) {
    t11 = jsx("title", {}, "Refsrepro | Index");
    $[24] = t11;
  } else {
    t11 = $[24];
  }
  let t12;
  if ($[25] === Symbol.for("react.memo_cache_sentinel")) {
    t12 = jsx("meta", {
      content: "favicon.ico",
      property: "og:image"
    });
    $[25] = t12;
  } else {
    t12 = $[25];
  }
  let t13;
  if ($[26] !== t10) {
    t13 = jsx(Fragment, t0, t10, t11, t12);
    $[26] = t10;
    $[27] = t13;
  } else {
    t13 = $[27];
  }
  return t13;
}
_s(Component, "AuZJTqP7TZumEk7fC8HjEkyYyy0=", false, function () {
  return [useRegisteredRef, useRegisteredRef, useRegisteredRef, useRegisteredRef, useStateContext, useRegisteredRef];
});
_c2 = Component;
Component.displayName = "Component(index)";
export default _c3 = _UNSAFE_withComponentProps(Component);
var _c2, _c3;
$RefreshReg$(_c2, "Component");
$RefreshReg$(_c3, "%default%");
if (import.meta.hot && !inWebWorker) {
  window.$RefreshReg$ = prevRefreshReg;
  window.$RefreshSig$ = prevRefreshSig;
  RefreshRuntime.__hmr_import(import.meta.url).then((currentExports) => {
    RefreshRuntime.registerExportsForReactRefresh("/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_cm/refsrepro_patch/.web/app/routes/_index.jsx", currentExports);
    import.meta.hot.accept((nextExports) => {
      if (!nextExports) return;
      "routes/_index" && window.__reactRouterRouteModuleUpdates.set("routes/_index", nextExports);
      const invalidateMessage = RefreshRuntime.validateRefreshBoundaryAndEnqueueUpdate(currentExports, nextExports, ["clientAction","clientLoader","clientMiddleware","handle","meta","links","shouldRevalidate"]);
      if (invalidateMessage) import.meta.hot.invalidate(invalidateMessage);
    });
  });
}
//# sourceMappingURL=data:application/json;base64,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QSxDQUFldEQ7QUFBQUE7QUFBQUE7QUFBQUEiLCJuYW1lcyI6WyJSZWZsZXhFdmVudCIsImFwcGx5RXZlbnRBY3Rpb25zIiwicmVmcyIsInVzZVJlZ2lzdGVyZWRSZWYiLCJCdXR0b24iLCJSYWRpeFRoZW1lc0J1dHRvbiIsIkZsZXgiLCJSYWRpeFRoZW1lc0ZsZXgiLCJIZWFkaW5nIiwiUmFkaXhUaGVtZXNIZWFkaW5nIiwiVGV4dCIsIlJhZGl4VGhlbWVzVGV4dCIsIlRleHRGaWVsZCIsIlJhZGl4VGhlbWVzVGV4dEZpZWxkIiwiYWRkRXZlbnRzIiwidXNlU3RhdGVDb250ZXh0IiwiRnJhZ21lbnQiLCJ1c2VFZmZlY3QiLCJqc3giLCJDb21wb25lbnQiLCJfcyIsIiQiLCJfYyIsIiRpIiwiU3ltYm9sIiwiZm9yIiwicmVmX2giLCJyZWZfdGFyZ2V0IiwicmVmX3JhdyIsInJlZl9jYWxsZm4iLCJyZWZsZXhfX19zdGF0ZV9fX19zdGF0ZV9fcmVmc3JlcHJvX19fcmVmc3JlcHJvX19fcyIsInJlZl9sb2ciLCJ0MCIsInQxIiwiYWxpZ24iLCJjbGFzc05hbWUiLCJkaXJlY3Rpb24iLCJnYXAiLCJ0MiIsImlkIiwicmVmIiwidDMiLCJSb290IiwidDQiLCJfZSIsInQ1IiwiYXJncyIsImN1cnJlbnQiLCJ2YWx1ZSIsImJ1dHRvbiIsImJ1dHRvbnMiLCJjbGllbnRYIiwiY2xpZW50WSIsImFsdEtleSIsImN0cmxLZXkiLCJtZXRhS2V5Iiwic2hpZnRLZXkiLCJvbkNsaWNrIiwidDYiLCJmdW5jdGlvbiIsInQ3IiwidDgiLCJhcyIsInQ5IiwibG9nX3J4X3N0YXRlXyIsInQxMCIsInQxMSIsInQxMiIsImNvbnRlbnQiLCJwcm9wZXJ0eSIsInQxMyIsImRpc3BsYXlOYW1lIiwiX2MzIiwiX1VOU0FGRV93aXRoQ29tcG9uZW50UHJvcHMiXSwiaWdub3JlTGlzdCI6W10sInNvdXJjZXMiOlsiX2luZGV4LmpzeCJdLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1JlZmxleEV2ZW50LGFwcGx5RXZlbnRBY3Rpb25zLHJlZnMsdXNlUmVnaXN0ZXJlZFJlZn0gZnJvbSBcIiQvdXRpbHMvc3RhdGVcIlxuaW1wb3J0IHtCdXR0b24gYXMgUmFkaXhUaGVtZXNCdXR0b24sRmxleCBhcyBSYWRpeFRoZW1lc0ZsZXgsSGVhZGluZyBhcyBSYWRpeFRoZW1lc0hlYWRpbmcsVGV4dCBhcyBSYWRpeFRoZW1lc1RleHQsVGV4dEZpZWxkIGFzIFJhZGl4VGhlbWVzVGV4dEZpZWxkfSBmcm9tIFwiQHJhZGl4LXVpL3RoZW1lc1wiXG5pbXBvcnQge2FkZEV2ZW50c30gZnJvbSBcIiQvdXRpbHMvY29udGV4dFwiXG5pbXBvcnQge3VzZVN0YXRlQ29udGV4dH0gZnJvbSBcIiQvdXRpbHMvY29udGV4dC1yZWdpc3RyeVwiXG5pbXBvcnQge0ZyYWdtZW50LHVzZUVmZmVjdH0gZnJvbSBcInJlYWN0XCJcbmltcG9ydCB7anN4fSBmcm9tIFwiQGVtb3Rpb24vcmVhY3RcIlxuXG5cblxuXG5cbmZ1bmN0aW9uIENvbXBvbmVudCgpIHtcbmNvbnN0IHJlZl9oID0gdXNlUmVnaXN0ZXJlZFJlZihcInJlZl9oXCIpO1xuY29uc3QgcmVmX3RhcmdldCA9IHVzZVJlZ2lzdGVyZWRSZWYoXCJyZWZfdGFyZ2V0XCIpO1xuY29uc3QgcmVmX3JhdyA9IHVzZVJlZ2lzdGVyZWRSZWYoXCJyZWZfcmF3XCIpO1xuY29uc3QgcmVmX2NhbGxmbiA9IHVzZVJlZ2lzdGVyZWRSZWYoXCJyZWZfY2FsbGZuXCIpO1xuY29uc3QgcmVmbGV4X19fc3RhdGVfX19fc3RhdGVfX3JlZnNyZXByb19fX3JlZnNyZXByb19fX3MgPSB1c2VTdGF0ZUNvbnRleHQoXCJyZWZsZXhfX19zdGF0ZV9fX19zdGF0ZS5yZWZzcmVwcm9fX19yZWZzcmVwcm9fX19zXCIpXG5jb25zdCByZWZfbG9nID0gdXNlUmVnaXN0ZXJlZFJlZihcInJlZl9sb2dcIik7XG5cbiAgcmV0dXJuIChcbiAgICBqc3goRnJhZ21lbnQse30sanN4KFJhZGl4VGhlbWVzRmxleCx7YWxpZ246XCJzdGFydFwiLGNsYXNzTmFtZTpcInJ4LVN0YWNrXCIsZGlyZWN0aW9uOlwiY29sdW1uXCIsZ2FwOlwiM1wifSxqc3goUmFkaXhUaGVtZXNIZWFkaW5nLHtpZDpcImhcIixyZWY6cmVmX2h9LFwicmVmcyByZXByb1wiKSxqc3goUmFkaXhUaGVtZXNUZXh0RmllbGQuUm9vdCx7aWQ6XCJ0YXJnZXRcIixyZWY6cmVmX3RhcmdldH0sKSxqc3goUmFkaXhUaGVtZXNCdXR0b24se2lkOlwicmF3XCIsb25DbGljazooKF9lKSA9PiAoKCguLi5hcmdzKSA9PiAoKCgpID0+IHsgcmVmc1sncmVmX3RhcmdldCddLmN1cnJlbnQudmFsdWUgPSAnc2V0IGJ5IHJhdyB2YXInOyB9KSgoeyBbXCJidXR0b25cIl0gOiBfZT8uW1wiYnV0dG9uXCJdLCBbXCJidXR0b25zXCJdIDogX2U/LltcImJ1dHRvbnNcIl0sIFtcImNsaWVudF94XCJdIDogX2U/LltcImNsaWVudFhcIl0sIFtcImNsaWVudF95XCJdIDogX2U/LltcImNsaWVudFlcIl0sIFtcImFsdF9rZXlcIl0gOiBfZT8uW1wiYWx0S2V5XCJdLCBbXCJjdHJsX2tleVwiXSA6IF9lPy5bXCJjdHJsS2V5XCJdLCBbXCJtZXRhX2tleVwiXSA6IF9lPy5bXCJtZXRhS2V5XCJdLCBbXCJzaGlmdF9rZXlcIl0gOiBfZT8uW1wic2hpZnRLZXlcIl0gfSksIC4uLmFyZ3MpKSkoX2UpKSkscmVmOnJlZl9yYXd9LFwicmF3IHZhciBoYW5kbGVyXCIpLGpzeChSYWRpeFRoZW1lc0J1dHRvbix7aWQ6XCJjYWxsZm5cIixvbkNsaWNrOigoX2UpID0+IChhZGRFdmVudHMoWyhSZWZsZXhFdmVudChcIl9jYWxsX2Z1bmN0aW9uXCIsICh7IFtcImZ1bmN0aW9uXCJdIDogKCkgPT4gcmVmc1sncmVmX3RhcmdldCddLmN1cnJlbnQudmFsdWUsIFtcImNhbGxiYWNrXCJdIDogXCIoX3Jlc3VsdCkgPT4ge2FkZEV2ZW50cyhbUmVmbGV4RXZlbnQoXFxcInJlZmxleF9fX3N0YXRlX19fX3N0YXRlLnJlZnNyZXByb19fX3JlZnNyZXByb19fX3Muc2V0X2xvZ1xcXCIsIHt2Ol9yZXN1bHR9KV0pfVwiIH0pLCAoeyAgfSkpKV0sIFtfZV0sICh7ICB9KSkpKSxyZWY6cmVmX2NhbGxmbn0sXCJjYWxsX2Z1bmN0aW9uXCIpLGpzeChSYWRpeFRoZW1lc1RleHQse2FzOlwicFwiLGlkOlwibG9nXCIscmVmOnJlZl9sb2d9LFwibG9nOiBcIixyZWZsZXhfX19zdGF0ZV9fX19zdGF0ZV9fcmVmc3JlcHJvX19fcmVmc3JlcHJvX19fcy5sb2dfcnhfc3RhdGVfKSksanN4KFwidGl0bGVcIix7fSxcIlJlZnNyZXBybyB8IEluZGV4XCIpLGpzeChcIm1ldGFcIix7Y29udGVudDpcImZhdmljb24uaWNvXCIscHJvcGVydHk6XCJvZzppbWFnZVwifSwpKVxuICApXG59XG5Db21wb25lbnQuZGlzcGxheU5hbWUgPSBcIkNvbXBvbmVudChpbmRleClcIjtcblxuZXhwb3J0IGRlZmF1bHQgQ29tcG9uZW50O1xuIl0sImZpbGUiOiIvdG1wL2NsYXVkZS0wLy1ob21lLXVzZXItcmVmbGV4L2U5MjlmNzkwLWI0MjUtNWM3My05OWJjLWIwMGNjYjA1ZGUyOS9zY3JhdGNocGFkL2FwcHMvdmVyaWZ5X2NtL3JlZnNyZXByb19wYXRjaC8ud2ViL2FwcC9yb3V0ZXMvX2luZGV4LmpzeCJ9