// Builds the pages the live tests load: plain Vite with the StyleX plugin, set
// up the way an app's build sets it up.

import { fileURLToPath } from "node:url";

import stylex from "@stylexjs/unplugin";
import { Features } from "lightningcss";
import { build } from "vite";

const ROOT = fileURLToPath(new URL("./", import.meta.url));

// The options Reflex gives StyleX in an app.
export const STYLEX_OPTIONS = {
  useCSSLayers: { prefix: "reflex-ui" },
  styleResolution: /** @type {const} */ ("application-order"),
  lightningcssOptions: { minify: true, exclude: Features.LightDark },
};

/**
 * Build entries of the harness.
 *
 * @param {string[]} entries The html or javascript files to build, relative to
 *   this directory.
 * @param {string} outDir Where the build goes.
 * @returns {Promise<void>}
 */
export async function buildHarness(entries, outDir) {
  await build({
    root: ROOT,
    base: "./",
    configFile: false,
    logLevel: "error",
    plugins: [stylex.vite(STYLEX_OPTIONS)],
    build: {
      outDir,
      emptyOutDir: true,
      rollupOptions: { input: entries.map((entry) => `${ROOT}${entry}`) },
    },
  });
}
