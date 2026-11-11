import { createHotContext as __vite__createHotContext } from "/@vite/client";import.meta.hot = __vite__createHotContext("/app/routes/[hook]._index.jsx");const Fragment = __vite__cjsImport3_react["Fragment"]; const useEffect = __vite__cjsImport3_react["useEffect"]; const useRef = __vite__cjsImport3_react["useRef"];import RefreshRuntime from "/@id/__x00__virtual:react-router/hmr-runtime";const inWebWorker = typeof WorkerGlobalScope !== 'undefined' && self instanceof WorkerGlobalScope;let prevRefreshReg;let prevRefreshSig;if (import.meta.hot && !inWebWorker) {  if (!window.__vite_plugin_react_preamble_installed__) {    throw new Error(      "React Router Vite plugin can't detect preamble. Something is wrong."    );  }  prevRefreshReg = window.$RefreshReg$;  prevRefreshSig = window.$RefreshSig$;  window.$RefreshReg$ = (type, id) => {    RefreshRuntime.register(type, "/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_cm/refsrepro_prev/.web/app/routes/[hook]._index.jsx" + " " + id)  };  window.$RefreshSig$ = RefreshRuntime.createSignatureFunctionForTransform;}var _s = $RefreshSig$();
import { UNSAFE_withComponentProps as _UNSAFE_withComponentProps } from "/node_modules/.vite/deps/react-router.js?v=91094fe3";
import __vite__cjsImport3_react from "/node_modules/.vite/deps/react.js?v=91094fe3";
import { refs } from "/utils/state.js";
import { Flex as RadixThemesFlex, Heading as RadixThemesHeading, TextField as RadixThemesTextField } from "/node_modules/.vite/deps/@radix-ui_themes.js?v=ed3d89a8";
import { jsx } from "/node_modules/.vite/deps/@emotion_react.js?v=7350cf2a";
function Component() {
  _s();
  const ref_h2 = useRef(null);
  refs["ref_h2"] = ref_h2;
  const ref_target = useRef(null);
  refs["ref_target"] = ref_target;
  useEffect(() => {
    refs["ref_target"].current.value = "set by hook";
  }, []);
  return jsx(Fragment, {}, jsx(RadixThemesFlex, {
    align: "start",
    className: "rx-Stack",
    direction: "column",
    gap: "3"
  }, jsx(RadixThemesHeading, {
    id: "h2",
    ref: ref_h2
  }, "hook page"), jsx(RadixThemesTextField.Root, {
    id: "target",
    ref: ref_target
  }), jsx(Fragment, {})), jsx("title", {}, "Refsrepro | Hook"), jsx("meta", {
    content: "favicon.ico",
    property: "og:image"
  }));
}
_s(Component, "bgYmdQk+KhmA1YwzW2hFfwY/AyA=");
_c = Component;
Component.displayName = "Component(hook)";
export default _c2 = _UNSAFE_withComponentProps(Component);
var _c, _c2;
$RefreshReg$(_c, "Component");
$RefreshReg$(_c2, "%default%");
if (import.meta.hot && !inWebWorker) {
  window.$RefreshReg$ = prevRefreshReg;
  window.$RefreshSig$ = prevRefreshSig;
  RefreshRuntime.__hmr_import(import.meta.url).then((currentExports) => {
    RefreshRuntime.registerExportsForReactRefresh("/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_cm/refsrepro_prev/.web/app/routes/[hook]._index.jsx", currentExports);
    import.meta.hot.accept((nextExports) => {
      if (!nextExports) return;
      "routes/[hook]._index" && window.__reactRouterRouteModuleUpdates.set("routes/[hook]._index", nextExports);
      const invalidateMessage = RefreshRuntime.validateRefreshBoundaryAndEnqueueUpdate(currentExports, nextExports, ["clientAction","clientLoader","clientMiddleware","handle","meta","links","shouldRevalidate"]);
      if (invalidateMessage) import.meta.hot.invalidate(invalidateMessage);
    });
  });
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJtYXBwaW5ncyI6Ijs7QUFBQSxTQUFRQSxVQUFTQyxXQUFVQyxjQUFhO0FBQ3hDLFNBQVFDLFlBQVc7QUFDbkIsU0FBUUMsUUFBUUMsaUJBQWdCQyxXQUFXQyxvQkFBbUJDLGFBQWFDLDRCQUEyQjtBQUN0RyxTQUFRQyxXQUFVO0FBTWxCLFNBQVNDLFlBQVk7RUFBQUMsRUFBQTtFQUNyQixNQUFNQyxTQUFTWCxPQUFPLElBQUk7RUFBR0MsS0FBSyxZQUFZVTtFQUM5QyxNQUFNQyxhQUFhWixPQUFPLElBQUk7RUFBR0MsS0FBSyxnQkFBZ0JXO0VBQ3REYixnQkFBZ0I7SUFBRUUsS0FBSyxhQUFhLENBQUNZLFFBQVFDLFFBQVE7RUFBZSxHQUFHLEVBQUU7RUFFdkUsT0FDRU4sSUFBSVYsVUFBUyxDQUFDLEdBQUVVLElBQUlMLGlCQUFnQjtJQUFDWSxPQUFNO0lBQVFDLFdBQVU7SUFBV0MsV0FBVTtJQUFTQyxLQUFJO0VBQUcsR0FBRVYsSUFBSUgsb0JBQW1CO0lBQUNjLElBQUc7SUFBS0MsS0FBSVQ7RUFBTSxHQUFFLFdBQVcsR0FBRUgsSUFBSUQscUJBQXFCYyxNQUFLO0lBQUNGLElBQUc7SUFBU0MsS0FBSVI7RUFBVSxDQUFFLEdBQUVKLElBQUlWLFVBQVMsQ0FBQyxDQUFFLENBQUMsR0FBRVUsSUFBSSxTQUFRLENBQUMsR0FBRSxrQkFBa0IsR0FBRUEsSUFBSSxRQUFPO0lBQUNjLFNBQVE7SUFBY0MsVUFBUztFQUFVLENBQUUsQ0FBQztBQUU1VTtBQUFBYixFQUFBLENBUlNEO0FBQUFBO0FBU1RBLFVBQVVlLGNBQWM7QUFFeEIsZUFBQUMsR0FBQSxHQUFBQywwQkFBQSxDQUFlakI7QUFBQUE7QUFBQUE7QUFBQUEiLCJuYW1lcyI6WyJGcmFnbWVudCIsInVzZUVmZmVjdCIsInVzZVJlZiIsInJlZnMiLCJGbGV4IiwiUmFkaXhUaGVtZXNGbGV4IiwiSGVhZGluZyIsIlJhZGl4VGhlbWVzSGVhZGluZyIsIlRleHRGaWVsZCIsIlJhZGl4VGhlbWVzVGV4dEZpZWxkIiwianN4IiwiQ29tcG9uZW50IiwiX3MiLCJyZWZfaDIiLCJyZWZfdGFyZ2V0IiwiY3VycmVudCIsInZhbHVlIiwiYWxpZ24iLCJjbGFzc05hbWUiLCJkaXJlY3Rpb24iLCJnYXAiLCJpZCIsInJlZiIsIlJvb3QiLCJjb250ZW50IiwicHJvcGVydHkiLCJkaXNwbGF5TmFtZSIsIl9jMiIsIl9VTlNBRkVfd2l0aENvbXBvbmVudFByb3BzIl0sImlnbm9yZUxpc3QiOltdLCJzb3VyY2VzIjpbIltob29rXS5faW5kZXguanN4Il0sInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7RnJhZ21lbnQsdXNlRWZmZWN0LHVzZVJlZn0gZnJvbSBcInJlYWN0XCJcbmltcG9ydCB7cmVmc30gZnJvbSBcIiQvdXRpbHMvc3RhdGVcIlxuaW1wb3J0IHtGbGV4IGFzIFJhZGl4VGhlbWVzRmxleCxIZWFkaW5nIGFzIFJhZGl4VGhlbWVzSGVhZGluZyxUZXh0RmllbGQgYXMgUmFkaXhUaGVtZXNUZXh0RmllbGR9IGZyb20gXCJAcmFkaXgtdWkvdGhlbWVzXCJcbmltcG9ydCB7anN4fSBmcm9tIFwiQGVtb3Rpb24vcmVhY3RcIlxuXG5cblxuXG5cbmZ1bmN0aW9uIENvbXBvbmVudCgpIHtcbmNvbnN0IHJlZl9oMiA9IHVzZVJlZihudWxsKTsgcmVmc1tcInJlZl9oMlwiXSA9IHJlZl9oMjtcbmNvbnN0IHJlZl90YXJnZXQgPSB1c2VSZWYobnVsbCk7IHJlZnNbXCJyZWZfdGFyZ2V0XCJdID0gcmVmX3RhcmdldDtcbnVzZUVmZmVjdCgoKSA9PiB7IHJlZnNbJ3JlZl90YXJnZXQnXS5jdXJyZW50LnZhbHVlID0gJ3NldCBieSBob29rJzsgfSwgW10pXG5cbiAgcmV0dXJuIChcbiAgICBqc3goRnJhZ21lbnQse30sanN4KFJhZGl4VGhlbWVzRmxleCx7YWxpZ246XCJzdGFydFwiLGNsYXNzTmFtZTpcInJ4LVN0YWNrXCIsZGlyZWN0aW9uOlwiY29sdW1uXCIsZ2FwOlwiM1wifSxqc3goUmFkaXhUaGVtZXNIZWFkaW5nLHtpZDpcImgyXCIscmVmOnJlZl9oMn0sXCJob29rIHBhZ2VcIiksanN4KFJhZGl4VGhlbWVzVGV4dEZpZWxkLlJvb3Qse2lkOlwidGFyZ2V0XCIscmVmOnJlZl90YXJnZXR9LCksanN4KEZyYWdtZW50LHt9LCkpLGpzeChcInRpdGxlXCIse30sXCJSZWZzcmVwcm8gfCBIb29rXCIpLGpzeChcIm1ldGFcIix7Y29udGVudDpcImZhdmljb24uaWNvXCIscHJvcGVydHk6XCJvZzppbWFnZVwifSwpKVxuICApXG59XG5Db21wb25lbnQuZGlzcGxheU5hbWUgPSBcIkNvbXBvbmVudChob29rKVwiO1xuXG5leHBvcnQgZGVmYXVsdCBDb21wb25lbnQ7XG4iXSwiZmlsZSI6Ii90bXAvY2xhdWRlLTAvLWhvbWUtdXNlci1yZWZsZXgvZTkyOWY3OTAtYjQyNS01YzczLTk5YmMtYjAwY2NiMDVkZTI5L3NjcmF0Y2hwYWQvYXBwcy92ZXJpZnlfY20vcmVmc3JlcHJvX3ByZXYvLndlYi9hcHAvcm91dGVzL1tob29rXS5faW5kZXguanN4In0=