import { transformAsync } from "@babel/core";
import reactCompiler from "babel-plugin-react-compiler";
const refs = {};
const cases = {
  plain: `import {useRef} from "react"; import {jsx} from "@emotion/react";
export function Component() { const x = useRef(null); return jsx("div", {ref: x}, "hi"); }`,
  refs_assign: `import {useRef} from "react"; import {jsx} from "@emotion/react"; import {refs} from "$/utils/state";
export function Component() { const ref_a = useRef(null); refs["ref_a"] = ref_a; return jsx("div", {id: "a", ref: ref_a}, "hi"); }`,
  state_hook: `import {jsx} from "@emotion/react"; import {useStateContext} from "$/utils/context-registry";
export function Component() { const s = useStateContext("x"); return jsx("div", {}, s.count); }`,
};
for (const [name, src] of Object.entries(cases)) {
  const logs = [];
  const r = await transformAsync(src, { filename: "/x/app/routes/_index.jsx", configFile: false, babelrc: false,
    parserOpts: { plugins: ["jsx"] },
    plugins: [[reactCompiler, { target: "19", compilationMode: "infer", panicThreshold: "none", logger: { logEvent: (f, e) => logs.push(e.kind + (e.detail ? ": " + (e.detail.reason || e.detail.description || "") : "")) } }]] });
  console.log(name, "compiled=", r.code.includes("_c("), "| events:", logs.slice(0, 4).join(" || ").slice(0, 300));
}
