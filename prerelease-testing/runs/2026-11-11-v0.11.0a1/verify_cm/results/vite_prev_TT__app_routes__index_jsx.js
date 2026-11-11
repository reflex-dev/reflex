import { createHotContext as __vite__createHotContext } from "/@vite/client";import.meta.hot = __vite__createHotContext("/app/routes/_index.jsx");const Fragment = __vite__cjsImport3_react["Fragment"]; const useEffect = __vite__cjsImport3_react["useEffect"]; const useRef = __vite__cjsImport3_react["useRef"];import RefreshRuntime from "/@id/__x00__virtual:react-router/hmr-runtime";const inWebWorker = typeof WorkerGlobalScope !== 'undefined' && self instanceof WorkerGlobalScope;let prevRefreshReg;let prevRefreshSig;if (import.meta.hot && !inWebWorker) {  if (!window.__vite_plugin_react_preamble_installed__) {    throw new Error(      "React Router Vite plugin can't detect preamble. Something is wrong."    );  }  prevRefreshReg = window.$RefreshReg$;  prevRefreshSig = window.$RefreshSig$;  window.$RefreshReg$ = (type, id) => {    RefreshRuntime.register(type, "/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_cm/refsrepro_prev/.web/app/routes/_index.jsx" + " " + id)  };  window.$RefreshSig$ = RefreshRuntime.createSignatureFunctionForTransform;}var _s = $RefreshSig$();
import { UNSAFE_withComponentProps as _UNSAFE_withComponentProps } from "/node_modules/.vite/deps/react-router.js?v=91094fe3";
import __vite__cjsImport3_react from "/node_modules/.vite/deps/react.js?v=91094fe3";
import { refs } from "/utils/state.js";
import { Flex as RadixThemesFlex, Heading as RadixThemesHeading, Text as RadixThemesText, TextField as RadixThemesTextField } from "/node_modules/.vite/deps/@radix-ui_themes.js?v=ed3d89a8";
import { Bare_comp_95d099bdf145eda55775eeb66f26c67b_17d1e908, Button_button_55721c0a70b19144a1937fce842c570d_17d1e908, Button_button_f02af905e9b730b8f0ba355e16246dcd_17d1e908 } from "/app_components/refsrepro/refsrepro.jsx";
import { jsx } from "/node_modules/.vite/deps/@emotion_react.js?v=7350cf2a";
function Component() {
  _s();
  const ref_h = useRef(null);
  refs["ref_h"] = ref_h;
  const ref_target = useRef(null);
  refs["ref_target"] = ref_target;
  const ref_log = useRef(null);
  refs["ref_log"] = ref_log;
  return jsx(Fragment, {}, jsx(RadixThemesFlex, {
    align: "start",
    className: "rx-Stack",
    direction: "column",
    gap: "3"
  }, jsx(RadixThemesHeading, {
    id: "h",
    ref: ref_h
  }, "refs repro"), jsx(RadixThemesTextField.Root, {
    id: "target",
    ref: ref_target
  }), jsx(Button_button_f02af905e9b730b8f0ba355e16246dcd_17d1e908, {}, "raw var handler"), jsx(Button_button_55721c0a70b19144a1937fce842c570d_17d1e908, {}, "call_function"), jsx(RadixThemesText, {
    as: "p",
    id: "log",
    ref: ref_log
  }, "log: ", jsx(Bare_comp_95d099bdf145eda55775eeb66f26c67b_17d1e908, {}))), jsx("title", {}, "Refsrepro | Index"), jsx("meta", {
    content: "favicon.ico",
    property: "og:image"
  }));
}
_s(Component, "6ebZcP+qZWFyV2LqAgQnI16K5/Q=");
_c = Component;
Component.displayName = "Component(index)";
export default _c2 = _UNSAFE_withComponentProps(Component);
var _c, _c2;
$RefreshReg$(_c, "Component");
$RefreshReg$(_c2, "%default%");
if (import.meta.hot && !inWebWorker) {
  window.$RefreshReg$ = prevRefreshReg;
  window.$RefreshSig$ = prevRefreshSig;
  RefreshRuntime.__hmr_import(import.meta.url).then((currentExports) => {
    RefreshRuntime.registerExportsForReactRefresh("/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_cm/refsrepro_prev/.web/app/routes/_index.jsx", currentExports);
    import.meta.hot.accept((nextExports) => {
      if (!nextExports) return;
      "routes/_index" && window.__reactRouterRouteModuleUpdates.set("routes/_index", nextExports);
      const invalidateMessage = RefreshRuntime.validateRefreshBoundaryAndEnqueueUpdate(currentExports, nextExports, ["clientAction","clientLoader","clientMiddleware","handle","meta","links","shouldRevalidate"]);
      if (invalidateMessage) import.meta.hot.invalidate(invalidateMessage);
    });
  });
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJtYXBwaW5ncyI6Ijs7QUFBQSxTQUFRQSxVQUFTQyxXQUFVQyxjQUFhO0FBQ3hDLFNBQVFDLFlBQVc7QUFDbkIsU0FBUUMsUUFBUUMsaUJBQWdCQyxXQUFXQyxvQkFBbUJDLFFBQVFDLGlCQUFnQkMsYUFBYUMsNEJBQTJCO0FBQzlILFNBQVFDLHFEQUFvREMseURBQXdEQywrREFBOEQ7QUFDbEwsU0FBUUMsV0FBVTtBQU1sQixTQUFTQyxZQUFZO0VBQUFDLEVBQUE7RUFDckIsTUFBTUMsUUFBUWhCLE9BQU8sSUFBSTtFQUFHQyxLQUFLLFdBQVdlO0VBQzVDLE1BQU1DLGFBQWFqQixPQUFPLElBQUk7RUFBR0MsS0FBSyxnQkFBZ0JnQjtFQUN0RCxNQUFNQyxVQUFVbEIsT0FBTyxJQUFJO0VBQUdDLEtBQUssYUFBYWlCO0VBRTlDLE9BQ0VMLElBQUlmLFVBQVMsQ0FBQyxHQUFFZSxJQUFJVixpQkFBZ0I7SUFBQ2dCLE9BQU07SUFBUUMsV0FBVTtJQUFXQyxXQUFVO0lBQVNDLEtBQUk7RUFBRyxHQUFFVCxJQUFJUixvQkFBbUI7SUFBQ2tCLElBQUc7SUFBSUMsS0FBSVI7RUFBSyxHQUFFLFlBQVksR0FBRUgsSUFBSUoscUJBQXFCZ0IsTUFBSztJQUFDRixJQUFHO0lBQVNDLEtBQUlQO0VBQVUsQ0FBRSxHQUFFSixJQUFJRCx5REFBd0QsQ0FBQyxHQUFFLGlCQUFpQixHQUFFQyxJQUFJRix5REFBd0QsQ0FBQyxHQUFFLGVBQWUsR0FBRUUsSUFBSU4saUJBQWdCO0lBQUNtQixJQUFHO0lBQUlILElBQUc7SUFBTUMsS0FBSU47RUFBTyxHQUFFLFNBQVFMLElBQUlILHFEQUFvRCxDQUFDLENBQUUsQ0FBQyxDQUFDLEdBQUVHLElBQUksU0FBUSxDQUFDLEdBQUUsbUJBQW1CLEdBQUVBLElBQUksUUFBTztJQUFDYyxTQUFRO0lBQWNDLFVBQVM7RUFBVSxDQUFFLENBQUM7QUFFcGxCO0FBQUFiLEVBQUEsQ0FSU0Q7QUFBQUE7QUFTVEEsVUFBVWUsY0FBYztBQUV4QixlQUFBQyxHQUFBLEdBQUFDLDBCQUFBLENBQWVqQjtBQUFBQTtBQUFBQTtBQUFBQSIsIm5hbWVzIjpbIkZyYWdtZW50IiwidXNlRWZmZWN0IiwidXNlUmVmIiwicmVmcyIsIkZsZXgiLCJSYWRpeFRoZW1lc0ZsZXgiLCJIZWFkaW5nIiwiUmFkaXhUaGVtZXNIZWFkaW5nIiwiVGV4dCIsIlJhZGl4VGhlbWVzVGV4dCIsIlRleHRGaWVsZCIsIlJhZGl4VGhlbWVzVGV4dEZpZWxkIiwiQmFyZV9jb21wXzk1ZDA5OWJkZjE0NWVkYTU1Nzc1ZWViNjZmMjZjNjdiXzE3ZDFlOTA4IiwiQnV0dG9uX2J1dHRvbl81NTcyMWMwYTcwYjE5MTQ0YTE5MzdmY2U4NDJjNTcwZF8xN2QxZTkwOCIsIkJ1dHRvbl9idXR0b25fZjAyYWY5MDVlOWI3MzBiOGYwYmEzNTVlMTYyNDZkY2RfMTdkMWU5MDgiLCJqc3giLCJDb21wb25lbnQiLCJfcyIsInJlZl9oIiwicmVmX3RhcmdldCIsInJlZl9sb2ciLCJhbGlnbiIsImNsYXNzTmFtZSIsImRpcmVjdGlvbiIsImdhcCIsImlkIiwicmVmIiwiUm9vdCIsImFzIiwiY29udGVudCIsInByb3BlcnR5IiwiZGlzcGxheU5hbWUiLCJfYzIiLCJfVU5TQUZFX3dpdGhDb21wb25lbnRQcm9wcyJdLCJpZ25vcmVMaXN0IjpbXSwic291cmNlcyI6WyJfaW5kZXguanN4Il0sInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7RnJhZ21lbnQsdXNlRWZmZWN0LHVzZVJlZn0gZnJvbSBcInJlYWN0XCJcbmltcG9ydCB7cmVmc30gZnJvbSBcIiQvdXRpbHMvc3RhdGVcIlxuaW1wb3J0IHtGbGV4IGFzIFJhZGl4VGhlbWVzRmxleCxIZWFkaW5nIGFzIFJhZGl4VGhlbWVzSGVhZGluZyxUZXh0IGFzIFJhZGl4VGhlbWVzVGV4dCxUZXh0RmllbGQgYXMgUmFkaXhUaGVtZXNUZXh0RmllbGR9IGZyb20gXCJAcmFkaXgtdWkvdGhlbWVzXCJcbmltcG9ydCB7QmFyZV9jb21wXzk1ZDA5OWJkZjE0NWVkYTU1Nzc1ZWViNjZmMjZjNjdiXzE3ZDFlOTA4LEJ1dHRvbl9idXR0b25fNTU3MjFjMGE3MGIxOTE0NGExOTM3ZmNlODQyYzU3MGRfMTdkMWU5MDgsQnV0dG9uX2J1dHRvbl9mMDJhZjkwNWU5YjczMGI4ZjBiYTM1NWUxNjI0NmRjZF8xN2QxZTkwOH0gZnJvbSBcIiQvYXBwX2NvbXBvbmVudHMvcmVmc3JlcHJvL3JlZnNyZXByb1wiXG5pbXBvcnQge2pzeH0gZnJvbSBcIkBlbW90aW9uL3JlYWN0XCJcblxuXG5cblxuXG5mdW5jdGlvbiBDb21wb25lbnQoKSB7XG5jb25zdCByZWZfaCA9IHVzZVJlZihudWxsKTsgcmVmc1tcInJlZl9oXCJdID0gcmVmX2g7XG5jb25zdCByZWZfdGFyZ2V0ID0gdXNlUmVmKG51bGwpOyByZWZzW1wicmVmX3RhcmdldFwiXSA9IHJlZl90YXJnZXQ7XG5jb25zdCByZWZfbG9nID0gdXNlUmVmKG51bGwpOyByZWZzW1wicmVmX2xvZ1wiXSA9IHJlZl9sb2c7XG5cbiAgcmV0dXJuIChcbiAgICBqc3goRnJhZ21lbnQse30sanN4KFJhZGl4VGhlbWVzRmxleCx7YWxpZ246XCJzdGFydFwiLGNsYXNzTmFtZTpcInJ4LVN0YWNrXCIsZGlyZWN0aW9uOlwiY29sdW1uXCIsZ2FwOlwiM1wifSxqc3goUmFkaXhUaGVtZXNIZWFkaW5nLHtpZDpcImhcIixyZWY6cmVmX2h9LFwicmVmcyByZXByb1wiKSxqc3goUmFkaXhUaGVtZXNUZXh0RmllbGQuUm9vdCx7aWQ6XCJ0YXJnZXRcIixyZWY6cmVmX3RhcmdldH0sKSxqc3goQnV0dG9uX2J1dHRvbl9mMDJhZjkwNWU5YjczMGI4ZjBiYTM1NWUxNjI0NmRjZF8xN2QxZTkwOCx7fSxcInJhdyB2YXIgaGFuZGxlclwiKSxqc3goQnV0dG9uX2J1dHRvbl81NTcyMWMwYTcwYjE5MTQ0YTE5MzdmY2U4NDJjNTcwZF8xN2QxZTkwOCx7fSxcImNhbGxfZnVuY3Rpb25cIiksanN4KFJhZGl4VGhlbWVzVGV4dCx7YXM6XCJwXCIsaWQ6XCJsb2dcIixyZWY6cmVmX2xvZ30sXCJsb2c6IFwiLGpzeChCYXJlX2NvbXBfOTVkMDk5YmRmMTQ1ZWRhNTU3NzVlZWI2NmYyNmM2N2JfMTdkMWU5MDgse30sKSkpLGpzeChcInRpdGxlXCIse30sXCJSZWZzcmVwcm8gfCBJbmRleFwiKSxqc3goXCJtZXRhXCIse2NvbnRlbnQ6XCJmYXZpY29uLmljb1wiLHByb3BlcnR5Olwib2c6aW1hZ2VcIn0sKSlcbiAgKVxufVxuQ29tcG9uZW50LmRpc3BsYXlOYW1lID0gXCJDb21wb25lbnQoaW5kZXgpXCI7XG5cbmV4cG9ydCBkZWZhdWx0IENvbXBvbmVudDtcbiJdLCJmaWxlIjoiL3RtcC9jbGF1ZGUtMC8taG9tZS11c2VyLXJlZmxleC9lOTI5Zjc5MC1iNDI1LTVjNzMtOTliYy1iMDBjY2IwNWRlMjkvc2NyYXRjaHBhZC9hcHBzL3ZlcmlmeV9jbS9yZWZzcmVwcm9fcHJldi8ud2ViL2FwcC9yb3V0ZXMvX2luZGV4LmpzeCJ9