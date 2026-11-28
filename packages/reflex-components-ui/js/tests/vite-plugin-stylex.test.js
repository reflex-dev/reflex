// @vitest-environment node
// The Vite plugin an app builds with, driven through the hooks Vite calls.
import { beforeEach, expect, test } from "vitest";

import stylex from "../src/vite-plugin-stylex.js";

const STYLESHEET = "__reflex_global_styles";

// The options `UIPlugin.get_vite_plugins()` writes into vite.config.js, with
// the mode pinned: a build compiles for production whatever runs the tests.
const OPTIONS = {
  dev: false,
  useCSSLayers: { prefix: "reflex-ui" },
  styleResolution: "application-order",
  lightningcssOptions: { minify: true },
};

// A page module as the Reflex compiler emits it: one declaration per distinct
// style, each followed by the constant that holds its class names, which an
// element joins with its own.
const PAGE = `import * as stylex from "@stylexjs/stylex"
import {jsx} from "@emotion/react"

const sx_b26ac4fb71 = stylex.create({ s: {"boxSizing": "border-box", "display": "block"} });
const sx_b26ac4fb71_c = stylex.props(sx_b26ac4fb71.s).className;
const sx_f49d6b3475 = stylex.create({ s: {"boxSizing": "border-box", "display": "block", "padding": "4px"} });
const sx_f49d6b3475_c = stylex.props(sx_f49d6b3475.s).className;

export default function Component() {
  return jsx("main",{},jsx("div",{className:sx_b26ac4fb71_c},"hello"),jsx("div",{className:"p-8" + " " + sx_f49d6b3475_c},"padded"))
}
`;

// What the build makes of it: the declarations become strings, there is no
// call into StyleX, and the rest of the module is as it was written.
const COMPILED_PAGE = `import * as stylex from "@stylexjs/stylex"
import {jsx} from "@emotion/react"

const sx_b26ac4fb71_c = {
  className: "x9f619 x1lliihq"
}.className;
const sx_f49d6b3475_c = {
  className: "x9f619 x1lliihq xfawy5m"
}.className;




export default function Component() {
  return jsx("main",{},jsx("div",{className:sx_b26ac4fb71_c},"hello"),jsx("div",{className:"p-8" + " " + sx_f49d6b3475_c},"padded"))
}
`;

// A module whose bound prop indexes the class names of its values.
const VARIANT = `import * as stylex from "@stylexjs/stylex"
import {jsx} from "@emotion/react"

const sx_0123456789 = stylex.create({ s: {"padding": "4px", "width": "var(--v0)"}, a0_0: {"color": "white"}, a0_1: {"color": "black", "opacity": 0.5}, a0: {"color": "black"} });
const sx_0123456789_c = stylex.props(sx_0123456789.s).className;
const sx_0123456789_0 = { __proto__: null, "solid": stylex.props(sx_0123456789.a0_0).className, "soft": stylex.props(sx_0123456789.a0_1).className };
const sx_0123456789_0d = stylex.props(sx_0123456789.a0).className;

export default function Component({kind, width}) {
  return jsx("div",{className:sx_0123456789_c + " " + (sx_0123456789_0[kind] ?? sx_0123456789_0d),style:({ "--v0": (width) ?? "initial" })},"hello")
}
`;

const COMPILED_VARIANT = `import * as stylex from "@stylexjs/stylex"
import {jsx} from "@emotion/react"

const sx_0123456789_c = {
  className: "xfawy5m xw9a5fd"
}.className;
const sx_0123456789_0 = {
  __proto__: null,
  "solid": {
    className: "x1awj2ng"
  }.className,
  "soft": {
    className: "x1mqxbix xbyyjgo"
  }.className
};
const sx_0123456789_0d = {
  className: "x1mqxbix"
}.className;




export default function Component({kind, width}) {
  return jsx("div",{className:sx_0123456789_c + " " + (sx_0123456789_0[kind] ?? sx_0123456789_0d),style:({ "--v0": (width) ?? "initial" })},"hello")
}
`;

// A module that calls StyleX outside the statements of the Reflex compiler.
const HANDWRITTEN = `import * as stylex from "@stylexjs/stylex"
import {jsx} from "@emotion/react"

const sx_b26ac4fb71 = stylex.create({ s: {"boxSizing": "border-box", "display": "block"} });
const sx_b26ac4fb71_c = stylex.props(sx_b26ac4fb71.s).className;
const own = stylex.create({ root: {"padding": "4px"} });

export default function Component() {
  return jsx("main",{...stylex.props(own.root)},jsx("div",{className:sx_b26ac4fb71_c},"hello"))
}
`;

const COMPILED_CSS =
  "@layer reflex-ui.priority1{.xfawy5m{padding:4px}}@layer reflex-ui.priority2{.x9f619{box-sizing:border-box}.x1lliihq{display:block}}";

// The chunk that links the stylesheet the styles are appended to.
const ROOT = {
  moduleIds: [
    "/app/.web/app/root.jsx",
    `/app/.web/styles/${STYLESHEET}.css?url`,
  ],
};

beforeEach(() => {
  // The unplugin keeps the styles of every build of the process.
  delete (/** @type {any} */ (globalThis).__stylex_unplugin_store);
});

/**
 * Find the plugin that has a hook.
 *
 * @param {ReturnType<typeof stylex>} plugins
 * @param {"transform" | "generateBundle" | "augmentChunkHash"} hook
 * @param {string} [name] The name of the plugin, when several have the hook.
 * @returns {any} The plugin.
 */
function withHook(plugins, hook, name) {
  const found = plugins.filter(
    (plugin) => plugin[hook] && (!name || plugin.name === name),
  );
  expect(found.map((plugin) => plugin.name)).toHaveLength(1);
  return found[0];
}

/**
 * Compile a module the way Vite does.
 *
 * @param {ReturnType<typeof stylex>} plugins
 * @param {string} code
 * @param {string} id
 * @returns {Promise<string>} The compiled module.
 */
async function transform(plugins, code, id) {
  const { transform } = withHook(plugins, "transform", "@stylexjs/unplugin");
  const handler =
    typeof transform === "function" ? transform : transform.handler;
  const result = await handler.call({}, code, id);
  return result.code;
}

test("a page folds to class name strings and leaves no call into StyleX", async () => {
  const plugins = stylex(STYLESHEET, OPTIONS);
  expect(
    await transform(plugins, PAGE, "/app/.web/app/routes/_index.jsx"),
  ).toBe(COMPILED_PAGE);
});

test("a prop and a value bound to state fold to a table of class names and a custom property", async () => {
  const plugins = stylex(STYLESHEET, OPTIONS);
  expect(
    await transform(plugins, VARIANT, "/app/.web/app/routes/_index.jsx"),
  ).toBe(COMPILED_VARIANT);
});

test("a module that uses StyleX elsewhere is compiled whole", async () => {
  const plugins = stylex(STYLESHEET, OPTIONS);
  expect(
    await transform(plugins, HANDWRITTEN, "/app/.web/app/own.jsx"),
  ).toBe(`import * as stylex from "@stylexjs/stylex";
import { jsx } from "@emotion/react";
const sx_b26ac4fb71_c = {
  className: "x9f619 x1lliihq"
}.className;
export default function Component() {
  return jsx("main", {
    ...{
      className: "xfawy5m"
    }
  }, jsx("div", {
    className: sx_b26ac4fb71_c
  }, "hello"));
}`);
});

test("a build compiles a module once, for every plugin and every name it has", async () => {
  const source = PAGE.replace('"padding": "4px"', '"padding": "9px"');
  const css = COMPILED_CSS.replace(
    ".xfawy5m{padding:4px}",
    ".xskserf{padding:9px}",
  );
  // React Router builds with two sets of plugins, and names a route twice.
  const first = stylex(STYLESHEET, OPTIONS);
  const second = stylex(STYLESHEET, OPTIONS);
  const route = "/app/.web/app/routes/once.jsx";
  /**
   * @param {ReturnType<typeof stylex>} plugins
   * @param {string} code
   * @param {string} id
   * @param {object} [context] What Vite binds the hook to.
   * @returns {Promise<{ code: string }>} What the hook returns.
   */
  const compile = (plugins, code, id, context = {}) =>
    withHook(plugins, "transform", "@stylexjs/unplugin").transform.call(
      context,
      code,
      id,
    );

  const [client, child, server] = await Promise.all([
    compile(first, source, `${route}?__react-router-build-client-route`),
    compile(second, source, route),
    compile(first, source, route),
  ]);
  expect(client.code).toBe(COMPILED_PAGE.replace("xfawy5m", "xskserf"));
  // One result: the module went through Babel once.
  expect(child).toBe(client);
  expect(server).toBe(client);
  // The styles are collected under each name, as a compile leaves them.
  const store = /** @type {any} */ (globalThis).__stylex_unplugin_store;
  expect([...store.rulesById.keys()]).toEqual([
    `${route}?__react-router-build-client-route`,
    route,
  ]);
  expect(withHook(second, "augmentChunkHash").augmentChunkHash(ROOT)).toBe(css);

  // Another source of the same file is another compile, and so is every
  // transform of a development server, where a module is compiled as it changes.
  const changed = await compile(first, PAGE, route);
  expect(changed.code).toBe(COMPILED_PAGE);
  const watching = { meta: { watchMode: true } };
  const served = await compile(first, PAGE, route, watching);
  expect(served).not.toBe(changed);
  expect(served.code).toBe(COMPILED_PAGE);
});

test("the styles are appended to the stylesheet, and the chunk that links it follows the rename", async () => {
  const plugins = stylex(STYLESHEET, OPTIONS);
  await transform(plugins, PAGE, "/app/.web/app/routes/_index.jsx");

  const oldName = `assets/${STYLESHEET}-AAAAAAAA.css`;
  const newName = `assets/${STYLESHEET}-BBBBBBBB.css`;
  /** @type {Record<string, any>} */
  const bundle = {
    "assets/other-CCCCCCCC.css": {
      type: "asset",
      fileName: "assets/other-CCCCCCCC.css",
      source: ".other{}",
    },
    [oldName]: { type: "asset", fileName: oldName, source: ".reset{}" },
    "assets/root-DDDDDDDD.js": {
      type: "chunk",
      code: `const href="/${oldName}";`,
      viteMetadata: {
        importedAssets: new Set([oldName]),
        importedCss: new Set(),
      },
    },
    "assets/_index-EEEEEEEE.js": {
      type: "chunk",
      code: "export default 1;",
      viteMetadata: { importedAssets: new Set(), importedCss: new Set() },
    },
  };
  /** @type {unknown[]} */
  const emitted = [];
  const context = {
    emitFile(/** @type {unknown} */ file) {
      emitted.push(file);
      return "reference";
    },
    getFileName: (/** @type {string} */ reference) =>
      reference === "reference" ? newName : undefined,
  };
  withHook(plugins, "generateBundle").generateBundle.call(context, {}, bundle);

  expect(emitted).toEqual([
    {
      type: "asset",
      name: `${STYLESHEET}.css`,
      source: `.reset{}\n${COMPILED_CSS}`,
    },
  ]);
  expect(Object.keys(bundle)).toEqual([
    "assets/other-CCCCCCCC.css",
    "assets/root-DDDDDDDD.js",
    "assets/_index-EEEEEEEE.js",
  ]);
  expect(bundle["assets/root-DDDDDDDD.js"].code).toBe(
    `const href="/${newName}";`,
  );
  // What React Router moves from the server build into the client build.
  expect(bundle["assets/root-DDDDDDDD.js"].viteMetadata.importedAssets).toEqual(
    new Set([newName]),
  );
  expect(
    bundle["assets/_index-EEEEEEEE.js"].viteMetadata.importedAssets,
  ).toEqual(new Set());
});

test("the chunk that links the stylesheet is named after the compiled styles", async () => {
  const plugins = stylex(STYLESHEET, OPTIONS);
  const plugin = withHook(plugins, "augmentChunkHash");
  expect(plugin.apply).toBe("build");
  const root = ROOT;
  const page = {
    moduleIds: [
      "/app/.web/app/routes/_index.jsx",
      "/app/.web/styles/other.css",
    ],
  };

  await transform(plugins, PAGE, "/app/.web/app/routes/_index.jsx");
  expect(plugin.augmentChunkHash(root)).toBe(COMPILED_CSS);
  // A chunk that does not hold the address keeps its name when a style changes.
  expect(plugin.augmentChunkHash(page)).toBe(undefined);

  await transform(
    plugins,
    PAGE.replace('"padding": "4px"', '"padding": "5px"'),
    "/app/.web/app/routes/_index.jsx",
  );
  expect(plugin.augmentChunkHash(root)).toBe(
    COMPILED_CSS.replace(".xfawy5m{padding:4px}", ".x14odnwx{padding:5px}"),
  );
});

test("the development server loads the styles from the client entry", () => {
  const plugins = stylex(STYLESHEET, OPTIONS);
  const [plugin] = plugins.filter(
    ({ name }) => name === "reflex-ui:stylex-dev",
  );
  expect(plugin.apply).toBe("serve");
  expect(
    plugin.transform?.("hydrate();", "/app/.web/app/entry.client.js"),
  ).toBe('import "virtual:stylex:runtime";\nhydrate();');
  expect(plugin.transform?.("render();", "/app/.web/app/root.jsx")).toBe(null);
  expect(
    plugin.transform?.(
      "x();",
      "/app/.web/node_modules/pkg/app/entry.client.mjs",
    ),
  ).toBe(null);
});
