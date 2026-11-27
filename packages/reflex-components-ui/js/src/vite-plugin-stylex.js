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
 * @property {(code: string, id: string) => string | null} [transform]
 * @property {() => string} [__stylexCollectCss] Internal to the unplugin: the
 *   stylesheet of every style compiled so far.
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
    ...plugins.map(keepRecordedAssets),
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
