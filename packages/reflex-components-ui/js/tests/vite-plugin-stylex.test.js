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
// style, and a literal `class_name` carried inside the `stylex.props` call.
const PAGE = `import * as stylex from "@stylexjs/stylex"
import {jsx} from "@emotion/react"

const sx_b26ac4fb71 = stylex.create({ s: {"boxSizing": "border-box", "display": "block"} });
const sx_f49d6b3475 = stylex.create({ s: {"boxSizing": "border-box", "display": "block", "padding": "4px"} });

export default function Component() {
  return jsx("main",{},jsx("div",{...stylex.props(sx_b26ac4fb71.s)},"hello"),jsx("div",{...stylex.props(sx_f49d6b3475.s, { $$css: true, className: "p-8" })},"padded"))
}
`;

const COMPILED_CSS =
  "@layer reflex-ui.priority1{.xfawy5m{padding:4px}}@layer reflex-ui.priority2{.x9f619{box-sizing:border-box}.x1lliihq{display:block}}";

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
  ).toBe(`import * as stylex from "@stylexjs/stylex";
import { jsx } from "@emotion/react";
export default function Component() {
  return jsx("main", {}, jsx("div", {
    ...{
      className: "x9f619 x1lliihq"
    }
  }, "hello"), jsx("div", {
    ...{
      className: "x9f619 x1lliihq xfawy5m p-8"
    }
  }, "padded"));
}`);
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
  const root = {
    moduleIds: [
      "/app/.web/app/root.jsx",
      `/app/.web/styles/${STYLESHEET}.css?url`,
    ],
  };
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
