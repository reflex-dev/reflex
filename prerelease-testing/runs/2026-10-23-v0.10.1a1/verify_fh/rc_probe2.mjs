// Isolating cases for the React Compiler bail-out (verify_fh / FS-2). Run with cwd = an app's .web.
import { transformAsync } from "@babel/core";
import reactCompiler from "babel-plugin-react-compiler";
const H = `import {useRef} from "react"; import {jsx} from "@emotion/react"; import {refs} from "$/utils/state";\n`;
const cases = {
  plain_div: `${H}export function Component() { return jsx("div", {}, "hi"); }`,
  useRef_as_ref_prop: `${H}export function Component() { const r = useRef(null); return jsx("div", {ref: r}, "hi"); }`,
  refs_assign_only: `${H}export function Component() { const ref_a = useRef(null); refs["ref_a"] = ref_a; return jsx("div", {}, "hi"); }`,
  refs_assign_and_ref: `${H}export function Component() { const ref_a = useRef(null); refs["ref_a"] = ref_a; return jsx("div", {id: "a", ref: ref_a}, "hi"); }`,
  refs_read_in_handler: `${H}export function Component() { return jsx("button", {onClick: () => refs["ref_a"]?.current?.focus()}, "hi"); }`,
  refs_assign_in_effect: `${H}import {useEffect} from "react"; export function Component() { const ref_a = useRef(null); useEffect(() => { refs["ref_a"] = ref_a; }, []); return jsx("div", {ref: ref_a}, "hi"); }`,
};
for (const [name, src] of Object.entries(cases)) {
  const ev = [];
  const r = await transformAsync(src, { filename: "/x/app/routes/_index.jsx", configFile: false, babelrc: false,
    parserOpts: { plugins: ["jsx"] },
    plugins: [[reactCompiler, { target: "19", compilationMode: "infer", panicThreshold: "none",
      logger: { logEvent: (f, e) => ev.push(e.kind + (e.detail ? ": " + (e.detail.reason || e.detail.description || e.detail.category || "") : "")) } }]] });
  console.log(name.padEnd(24), "compiled=", r.code.includes("_c("), "|", ev.map(s => s.split("\n")[0].slice(0, 110)).join(" || "));
}
