/** Run after `reflex export`: node --test tests/frontend_quality.test.mjs. */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const web = process.env.REFLEX_WEB_WORKDIR || path.join(root, "docs/app/.web");
const require = createRequire(path.join(web, "package.json"));
const resolve = (name) => pathToFileURL(require.resolve(name)).href;

// Use the exact React and production bundler versions installed by Reflex.
test("Shiki server rendering includes escaped, readable code", async () => {
  const { createElement } = await import(resolve("react"));
  const { renderToStaticMarkup } = await import(resolve("react-dom/server"));
  const filename = path.join(root, "packages/reflex-base/src/reflex_base/.templates/web/components/shiki/code.js");
  const source = (await readFile(filename, "utf8"))
    .replaceAll('from "react"', `from "${resolve("react")}"`)
    .replaceAll('from "shiki"', `from "${resolve("shiki")}"`);
  const { Code } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
  const html = renderToStaticMarkup(createElement(Code, {code: 'print("<hello>")\n', language: "python", theme: "one-light"}));
  assert.match(html, /<pre/);
  assert.match(html, /&lt;hello&gt;/);
  assert.match(html, /class="line"/);
});

test("bundles discard unused memos and preserve custom wrapper side effects", async () => {
  const { rolldown } = await import(resolve("rolldown"));
  const source = execFileSync("uv", ["run", "--no-sync", "python", "-c", `
import reflex as rx
from reflex_base.compiler.templates import _render_memo_component
print('import {memo} from "react";')
print('function track(fn) { globalThis.customWrapperRan = true; return fn; }')
for name, wrapper in [('Used', 'memo'), ('Unused', 'memo'), ('Tracked', 'track')]:
    print(_render_memo_component(dict(name=name, display_name=name, signature='', render=rx.el.div(name.upper()+'_PAYLOAD').render(), hooks={}, wrapper=wrapper, pure_wrapper=wrapper == 'memo')))
`], {cwd: root, encoding: "utf8"});
  const bundle = await rolldown({
    input: "entry", external: ["react"],
    plugins: [{ name: "fixture", resolveId: (id) => id, load: (id) => id === "entry" ? 'import {Used} from "fixture"; globalThis.result=Used;' : source }],
  });
  try {
    const { output } = await bundle.generate({format: "es"});
    assert(!output[0].code.includes("UNUSED_PAYLOAD"));
    assert(output[0].code.includes("USED_PAYLOAD"));
    assert(output[0].code.includes("displayName"));
    assert(output[0].code.includes("customWrapperRan"));
  } finally {
    await bundle.close();
  }
});

test("optional registries load on demand, share requests, and retry failures", async () => {
  const rootCode = execFileSync("uv", ["run", "--no-sync", "python", "-c", `
from unittest.mock import patch
import reflex as rx
from reflex.compiler.compiler import compile_app_root
from reflex_base.components.dynamic import bundle_library
from reflex_base.registry import RegistrationContext
with RegistrationContext(), patch('reflex.compiler.compiler.get_config', return_value=rx.Config(app_name='quality', frontend_lazy_bundled_libraries=True)):
    bundle_library('quality-lazy-fixture')
    print(compile_app_root(rx.el.div('Quality'))[1])
`], {cwd: root, encoding: "utf8"});
  const setup = new Function("window", "React", "emotion_react", "utils_context", "utils_state", "loadFixture",
    rootCode.replace(/^import .*$/gm, "")
      .replace(/^export default function/gm, "function")
      .replace(/^export /gm, "")
      .replace('import("quality-lazy-fixture")', 'loadFixture()'));
  const stateSource = await readFile(path.join(root, "packages/reflex-base/src/reflex_base/.templates/web/utils/state.js"), "utf8");
  const evaluateSource = stateSource.split("export const evalReactComponent = ")[1].split("\n};")[0] + "\n}";
  const evaluate = new Function(`return (${evaluateSource});`)();
  const previousWindow = globalThis.window;
  const react = {quality: "same React instance"};
  try {
    let calls = 0;
    globalThis.window = {};
    setup(window, react, {}, {}, {}, async () => {calls++; return {value: 42};});
    assert.equal(calls, 0);
    assert.equal(window.__reflex.react, react);
    assert.equal(window.__reflex["quality-lazy-fixture"], undefined);
    const source = 'const {value} = window.__reflex["quality-lazy-fixture"]; export default function Quality(){ return value; }';
    const components = await Promise.all([evaluate(source), evaluate(source)]);
    assert.equal(calls, 1);
    assert.deepEqual(components.map(component => component()), [42, 42]);
    assert.equal(window.React, react);
    await evaluate(source);
    assert.equal(calls, 1);

    let attempts = 0;
    globalThis.window = {};
    setup(window, react, {}, {}, {}, async () => {
      if (++attempts === 1) throw new Error("Temporary download failure");
      return {value: 43};
    });
    await assert.rejects(evaluate(source), /Temporary download failure/);
    const recovered = await evaluate(source + "\n// retry fixture");
    assert.equal(attempts, 2);
    assert.equal(recovered(), 43);

    globalThis.window = {__reflex: {react}};
    const legacy = await evaluate('export default function Legacy(){ return window.__reflex.react.quality; }');
    assert.equal(legacy(), "same React instance");
  } finally {
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
  }
});
