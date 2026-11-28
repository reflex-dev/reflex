// The StyleX Vite plugin, adapted to the React Router build of a Reflex app.
//
// StyleX appends the styles it compiled to a stylesheet of the build once every
// chunk is rendered and named, and gives that stylesheet a new name. Three
// things around that are put right here:
//
// - React Router has recorded the old name by then, and fails when it moves
//   the assets of the server build.
// - A chunk that holds the address of the stylesheet is edited after its own
//   name was derived from its content, so a change of style would alter the
//   chunk under an unchanged name, and a cached copy would ask for a
//   stylesheet that is gone.
// - React Router renders the document itself, so nothing loads the module
//   through which StyleX delivers the styles while developing.
// - React Router builds a route module several times, for the client, for the
//   server and for reading its exports, and StyleX compiles it with Babel
//   each time. A build compiles each module once and reuses the result.
// - StyleX compiles a module by parsing and printing all of it with Babel,
//   which costs more than the rest of the build spends on a page. The Reflex
//   compiler writes the styles of a module as statements of their own, so
//   only those are handed to StyleX, and the page around them is left as it is.

import { basename } from "node:path";

import stylexUnplugin from "@stylexjs/unplugin";

// The module of the unplugin that fetches the compiled styles in development
// and fetches them again when one changes.
const DEV_RUNTIME = "virtual:stylex:runtime";

// The module of an app that runs first in the browser.
const CLIENT_ENTRY = /\/app\/entry\.client\.[jt]sx?$/;

/**
 * The hooks of a Vite plugin that are used here.
 *
 * @typedef {object} VitePlugin
 * @property {string} name
 * @property {"serve" | "build"} [apply]
 * @property {(this: any, outputOptions: unknown, bundle: Bundle) => void} [generateBundle]
 * @property {(chunk: { moduleIds: string[] }) => string | void} [augmentChunkHash]
 * @property {(this: any, code: string, id: string) => any} [transform]
 * @property {() => string} [__stylexCollectCss] Internal to the unplugin: the
 *   stylesheet of every style compiled so far.
 * @property {() => { rulesById: Map<string, unknown> }} [__stylexGetSharedStore]
 *   Internal to the unplugin: the styles of every module compiled so far, which
 *   every plugin of the process collects from.
 */

/**
 * The files of a build, by name.
 *
 * @typedef {Record<string, { viteMetadata?: { importedAssets?: Set<string> } }>} Bundle
 */

/**
 * Keep the assets a chunk has recorded in step with the stylesheet StyleX
 * renames.
 *
 * @param {VitePlugin} plugin A plugin of the StyleX unplugin.
 * @returns {VitePlugin} The plugin, its `generateBundle` wrapped.
 */
function keepRecordedAssets(plugin) {
  const generateBundle = plugin.generateBundle;
  if (typeof generateBundle !== "function") return plugin;
  return {
    ...plugin,
    generateBundle(outputOptions, bundle) {
      const stylesheets = Object.keys(bundle).filter((name) =>
        name.endsWith(".css"),
      );
      // Rolldown does not expose a file emitted in this hook through `bundle`,
      // so record the name the unplugin asks for instead.
      /** @type {string | undefined} */
      let renamedTo;
      const context = new Proxy(this, {
        get(target, key) {
          const value = Reflect.get(target, key, target);
          if (key === "getFileName") {
            return (/** @type {string} */ referenceId) =>
              (renamedTo = value.call(target, referenceId));
          }
          return typeof value === "function" ? value.bind(target) : value;
        },
      });
      generateBundle.call(context, outputOptions, bundle);
      const removed = stylesheets.filter((name) => !(name in bundle));
      if (removed.length !== 1 || !renamedTo) return;
      for (const item of Object.values(bundle)) {
        const assets = item.viteMetadata?.importedAssets;
        if (assets?.delete(removed[0])) assets.add(renamedTo);
      }
    },
  };
}

// The import and the statements the Reflex compiler writes for the styles of a
// module (`reflex_components_ui.style.emit`): each on a line of its own, named
// after its content.
const STYLEX_IMPORT = 'import * as stylex from "@stylexjs/stylex"';
const DECLARATION = /^const sx_[0-9a-f]{10}\w* = .*;$/gm;

/**
 * Hand StyleX the styles of a module without the module around them.
 *
 * @param {VitePlugin} plugin A plugin of the StyleX unplugin.
 * @returns {VitePlugin} The plugin, its `transform` compiling the statements
 *   that declare styles and leaving the rest of the module untouched. A
 *   module that uses StyleX anywhere else is compiled whole.
 */
function compileDeclarations(plugin) {
  const transform = plugin.transform;
  if (typeof transform !== "function") return plugin;
  return {
    ...plugin,
    async transform(code, id) {
      const declarations = code.match(DECLARATION);
      const rest = declarations
        ? code.replace(STYLEX_IMPORT, "").replace(DECLARATION, "")
        : code;
      if (!declarations || /\bstylex\b/.test(rest))
        return transform.call(this, code, id);
      const result = await transform.call(
        this,
        `${STYLEX_IMPORT};\n${declarations.join("\n")}`,
        id,
      );
      const [first, ...compiled] = String(result?.code).split("\n");
      // Not the module that was handed over: compile the whole one instead.
      if (first !== `${STYLEX_IMPORT};`) return transform.call(this, code, id);
      let placed = false;
      return {
        code: code.replace(DECLARATION, () => {
          if (placed) return "";
          placed = true;
          return compiled.join("\n");
        }),
        map: null,
      };
    },
  };
}

// What StyleX made of each module of this process: the compiled module and
// the styles found in it, by the file and its source. Every plugin of a build
// shares it, as React Router creates more than one.
/** @type {Map<string, Promise<{ result: unknown, rules: unknown }>>} */
const compiled = new Map();

/**
 * Compile a module once in a build, however often it is transformed.
 *
 * @param {VitePlugin} plugin A plugin of the StyleX unplugin.
 * @returns {VitePlugin} The plugin, its `transform` reusing earlier results.
 */
function compileOnce(plugin) {
  const transform = plugin.transform;
  const store = plugin.__stylexGetSharedStore;
  if (typeof transform !== "function" || typeof store !== "function")
    return plugin;
  return {
    ...plugin,
    transform(code, id) {
      // A development server compiles a module again when it changes, and
      // the unplugin skips a module that does not mention StyleX.
      if (this?.meta?.watchMode || !code.includes("stylex"))
        return transform.call(this, code, id);
      const key = `${id.split("?")[0]}\0${code}`;
      const earlier = compiled.get(key);
      if (earlier) {
        return earlier.then(({ result, rules }) => {
          // The styles are collected under the name of each module.
          const { rulesById } = store();
          if (rules) rulesById.set(id, rules);
          else rulesById.delete(id);
          return result;
        });
      }
      const first = Promise.resolve(transform.call(this, code, id)).then(
        (result) => ({ result, rules: store().rulesById.get(id) }),
      );
      compiled.set(key, first);
      // A failed compile is reported by each transform, not remembered.
      first.catch(() => compiled.delete(key));
      return first.then(({ result }) => result);
    },
  };
}

/**
 * Compile the StyleX styles of a Reflex app into one of its stylesheets.
 *
 * @param {string} stylesheet The name, without its extension, of the
 *   stylesheet the compiled styles are appended to.
 * @param {Record<string, unknown>} [options] Options of `@stylexjs/unplugin`.
 * @returns {VitePlugin[]} The plugins to add to the Vite configuration.
 */
export default function stylex(stylesheet, options) {
  /** @type {VitePlugin[]} */
  const plugins = [
    stylexUnplugin.vite({
      ...options,
      cssInjectionTarget: (/** @type {string} */ fileName) =>
        basename(fileName).startsWith(stylesheet),
    }),
  ].flat();
  const collectors = plugins.flatMap(
    (plugin) => plugin.__stylexCollectCss ?? [],
  );
  if (collectors.length === 0) {
    throw new Error(
      "reflex-ui: @stylexjs/unplugin no longer exposes the styles it collected (__stylexCollectCss), which the names of the built files depend on. Install the version of @stylexjs/unplugin that reflex-components-ui pins.",
    );
  }
  return [
    ...plugins
      .map(keepRecordedAssets)
      .map(compileDeclarations)
      .map(compileOnce),
    {
      name: "reflex-ui:stylex-hash",
      apply: "build",
      // The chunk that holds the address of the stylesheet is named after the
      // styles too, as they are what moves that address.
      augmentChunkHash(chunk) {
        const holdsAddress = chunk.moduleIds.some(
          (id) => basename(id.split("?")[0]) === `${stylesheet}.css`,
        );
        if (holdsAddress)
          return collectors.map((collect) => collect()).join("");
      },
    },
    {
      name: "reflex-ui:stylex-dev",
      apply: "serve",
      transform(code, id) {
        if (!CLIENT_ENTRY.test(id)) return null;
        return `import ${JSON.stringify(DEV_RUNTIME)};\n${code}`;
      },
    },
  ];
}
