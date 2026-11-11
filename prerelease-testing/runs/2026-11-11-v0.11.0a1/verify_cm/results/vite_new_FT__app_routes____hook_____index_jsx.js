import { createHotContext as __vite__createHotContext } from "/@vite/client";import.meta.hot = __vite__createHotContext("/app/routes/[hook]._index.jsx");const _c = __vite__cjsImport3_react_compilerRuntime["c"];const Fragment = __vite__cjsImport7_react["Fragment"]; const useEffect = __vite__cjsImport7_react["useEffect"];import RefreshRuntime from "/@id/__x00__virtual:react-router/hmr-runtime";const inWebWorker = typeof WorkerGlobalScope !== 'undefined' && self instanceof WorkerGlobalScope;let prevRefreshReg;let prevRefreshSig;if (import.meta.hot && !inWebWorker) {  if (!window.__vite_plugin_react_preamble_installed__) {    throw new Error(      "React Router Vite plugin can't detect preamble. Something is wrong."    );  }  prevRefreshReg = window.$RefreshReg$;  prevRefreshSig = window.$RefreshSig$;  window.$RefreshReg$ = (type, id) => {    RefreshRuntime.register(type, "/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_cm/refsrepro/.web/app/routes/[hook]._index.jsx" + " " + id)  };  window.$RefreshSig$ = RefreshRuntime.createSignatureFunctionForTransform;}var _s = $RefreshSig$();
import { UNSAFE_withComponentProps as _UNSAFE_withComponentProps } from "/node_modules/.vite/deps/react-router.js?v=6a5e93ff";
import __vite__cjsImport3_react_compilerRuntime from "/node_modules/.vite/deps/react_compiler-runtime.js?v=6a5e93ff";
import { refs, useRegisteredRef } from "/utils/state.js";
import { Flex as RadixThemesFlex, Heading as RadixThemesHeading, TextField as RadixThemesTextField } from "/node_modules/.vite/deps/@radix-ui_themes.js?v=6a5e93ff";
import { Refhook_fragment_a4beb949c8d4266d03a48b33dbcf0b0e_17d1e908 } from "/app_components/refsrepro/refsrepro.jsx";
import __vite__cjsImport7_react from "/node_modules/.vite/deps/react.js?v=6a5e93ff";
import { jsx } from "/node_modules/.vite/deps/@emotion_react.js?v=6a5e93ff";
function Component() {
  _s();
  const $ = _c(15);
  if ($[0] !== "49ae598bf9efd3592b17e64b6ee8b98d8c6f56103aa1f603db6056142aa1caa1") {
    for (let $i = 0; $i < 15; $i += 1) {
      $[$i] = Symbol.for("react.memo_cache_sentinel");
    }
    $[0] = "49ae598bf9efd3592b17e64b6ee8b98d8c6f56103aa1f603db6056142aa1caa1";
  }
  const ref_h2 = useRegisteredRef("ref_h2");
  const ref_target = useRegisteredRef("ref_target");
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
  if ($[3] !== ref_h2) {
    t2 = jsx(RadixThemesHeading, {
      id: "h2",
      ref: ref_h2
    }, "hook page");
    $[3] = ref_h2;
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
    t4 = jsx(Refhook_fragment_a4beb949c8d4266d03a48b33dbcf0b0e_17d1e908, {});
    $[7] = t4;
  } else {
    t4 = $[7];
  }
  let t5;
  if ($[8] !== t2 || $[9] !== t3) {
    t5 = jsx(RadixThemesFlex, t1, t2, t3, t4);
    $[8] = t2;
    $[9] = t3;
    $[10] = t5;
  } else {
    t5 = $[10];
  }
  let t6;
  if ($[11] === Symbol.for("react.memo_cache_sentinel")) {
    t6 = jsx("title", {}, "Refsrepro | Hook");
    $[11] = t6;
  } else {
    t6 = $[11];
  }
  let t7;
  if ($[12] === Symbol.for("react.memo_cache_sentinel")) {
    t7 = jsx("meta", {
      content: "favicon.ico",
      property: "og:image"
    });
    $[12] = t7;
  } else {
    t7 = $[12];
  }
  let t8;
  if ($[13] !== t5) {
    t8 = jsx(Fragment, t0, t5, t6, t7);
    $[13] = t5;
    $[14] = t8;
  } else {
    t8 = $[14];
  }
  return t8;
}
_s(Component, "KSh4Pl5jsvSIF2TcugQE7QOYekY=", false, function () {
  return [useRegisteredRef, useRegisteredRef];
});
_c2 = Component;
Component.displayName = "Component(hook)";
export default _c3 = _UNSAFE_withComponentProps(Component);
var _c2, _c3;
$RefreshReg$(_c2, "Component");
$RefreshReg$(_c3, "%default%");
if (import.meta.hot && !inWebWorker) {
  window.$RefreshReg$ = prevRefreshReg;
  window.$RefreshSig$ = prevRefreshSig;
  RefreshRuntime.__hmr_import(import.meta.url).then((currentExports) => {
    RefreshRuntime.registerExportsForReactRefresh("/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_cm/refsrepro/.web/app/routes/[hook]._index.jsx", currentExports);
    import.meta.hot.accept((nextExports) => {
      if (!nextExports) return;
      "routes/[hook]._index" && window.__reactRouterRouteModuleUpdates.set("routes/[hook]._index", nextExports);
      const invalidateMessage = RefreshRuntime.validateRefreshBoundaryAndEnqueueUpdate(currentExports, nextExports, ["clientAction","clientLoader","clientMiddleware","handle","meta","links","shouldRevalidate"]);
      if (invalidateMessage) import.meta.hot.invalidate(invalidateMessage);
    });
  });
}
//# sourceMappingURL=data:application/json;base64,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QUQ3WCxPQUNFd0I7QUFDRDtBQUFBekIsRUFBQSxDQU5IRDtFQUFBQSxRQUNlWCxrQkFDSUE7QUFBQUE7QUFBQUEsTUFGbkJXO0FBUUFBLFVBQVUyQixjQUFjO0FBRXhCLGVBQUFDLEdBQUEsR0FBQUMsMEJBQUEsQ0FBZTdCO0FBQUFBO0FBQUFBO0FBQUFBIiwibmFtZXMiOlsicmVmcyIsInVzZVJlZ2lzdGVyZWRSZWYiLCJGbGV4IiwiUmFkaXhUaGVtZXNGbGV4IiwiSGVhZGluZyIsIlJhZGl4VGhlbWVzSGVhZGluZyIsIlRleHRGaWVsZCIsIlJhZGl4VGhlbWVzVGV4dEZpZWxkIiwiUmVmaG9va19mcmFnbWVudF9hNGJlYjk0OWM4ZDQyNjZkMDNhNDhiMzNkYmNmMGIwZV8xN2QxZTkwOCIsIkZyYWdtZW50IiwidXNlRWZmZWN0IiwianN4IiwiQ29tcG9uZW50IiwiX3MiLCIkIiwiX2MiLCIkaSIsIlN5bWJvbCIsImZvciIsInJlZl9oMiIsInJlZl90YXJnZXQiLCJ0MCIsInQxIiwiYWxpZ24iLCJjbGFzc05hbWUiLCJkaXJlY3Rpb24iLCJnYXAiLCJ0MiIsImlkIiwicmVmIiwidDMiLCJSb290IiwidDQiLCJ0NSIsInQ2IiwidDciLCJjb250ZW50IiwicHJvcGVydHkiLCJ0OCIsImRpc3BsYXlOYW1lIiwiX2MzIiwiX1VOU0FGRV93aXRoQ29tcG9uZW50UHJvcHMiXSwiaWdub3JlTGlzdCI6W10sInNvdXJjZXMiOlsiW2hvb2tdLl9pbmRleC5qc3giXSwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtyZWZzLHVzZVJlZ2lzdGVyZWRSZWZ9IGZyb20gXCIkL3V0aWxzL3N0YXRlXCJcbmltcG9ydCB7RmxleCBhcyBSYWRpeFRoZW1lc0ZsZXgsSGVhZGluZyBhcyBSYWRpeFRoZW1lc0hlYWRpbmcsVGV4dEZpZWxkIGFzIFJhZGl4VGhlbWVzVGV4dEZpZWxkfSBmcm9tIFwiQHJhZGl4LXVpL3RoZW1lc1wiXG5pbXBvcnQge1JlZmhvb2tfZnJhZ21lbnRfYTRiZWI5NDljOGQ0MjY2ZDAzYTQ4YjMzZGJjZjBiMGVfMTdkMWU5MDh9IGZyb20gXCIkL2FwcF9jb21wb25lbnRzL3JlZnNyZXByby9yZWZzcmVwcm9cIlxuaW1wb3J0IHtGcmFnbWVudCx1c2VFZmZlY3R9IGZyb20gXCJyZWFjdFwiXG5pbXBvcnQge2pzeH0gZnJvbSBcIkBlbW90aW9uL3JlYWN0XCJcblxuXG5cblxuXG5mdW5jdGlvbiBDb21wb25lbnQoKSB7XG5jb25zdCByZWZfaDIgPSB1c2VSZWdpc3RlcmVkUmVmKFwicmVmX2gyXCIpO1xuY29uc3QgcmVmX3RhcmdldCA9IHVzZVJlZ2lzdGVyZWRSZWYoXCJyZWZfdGFyZ2V0XCIpO1xuXG4gIHJldHVybiAoXG4gICAganN4KEZyYWdtZW50LHt9LGpzeChSYWRpeFRoZW1lc0ZsZXgse2FsaWduOlwic3RhcnRcIixjbGFzc05hbWU6XCJyeC1TdGFja1wiLGRpcmVjdGlvbjpcImNvbHVtblwiLGdhcDpcIjNcIn0sanN4KFJhZGl4VGhlbWVzSGVhZGluZyx7aWQ6XCJoMlwiLHJlZjpyZWZfaDJ9LFwiaG9vayBwYWdlXCIpLGpzeChSYWRpeFRoZW1lc1RleHRGaWVsZC5Sb290LHtpZDpcInRhcmdldFwiLHJlZjpyZWZfdGFyZ2V0fSwpLGpzeChSZWZob29rX2ZyYWdtZW50X2E0YmViOTQ5YzhkNDI2NmQwM2E0OGIzM2RiY2YwYjBlXzE3ZDFlOTA4LHt9LCkpLGpzeChcInRpdGxlXCIse30sXCJSZWZzcmVwcm8gfCBIb29rXCIpLGpzeChcIm1ldGFcIix7Y29udGVudDpcImZhdmljb24uaWNvXCIscHJvcGVydHk6XCJvZzppbWFnZVwifSwpKVxuICApXG59XG5Db21wb25lbnQuZGlzcGxheU5hbWUgPSBcIkNvbXBvbmVudChob29rKVwiO1xuXG5leHBvcnQgZGVmYXVsdCBDb21wb25lbnQ7XG4iXSwiZmlsZSI6Ii90bXAvY2xhdWRlLTAvLWhvbWUtdXNlci1yZWZsZXgvZTkyOWY3OTAtYjQyNS01YzczLTk5YmMtYjAwY2NiMDVkZTI5L3NjcmF0Y2hwYWQvYXBwcy92ZXJpZnlfY20vcmVmc3JlcHJvLy53ZWIvYXBwL3JvdXRlcy9baG9va10uX2luZGV4LmpzeCJ9