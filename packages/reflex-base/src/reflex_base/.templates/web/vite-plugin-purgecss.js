/* vite-plugin-purgecss.js
 *
 * Remove unused CSS selectors from production bundles.  The primary target
 * is @radix-ui/themes/styles.css which weighs ~200 KB and includes styles
 * for every Radix component, even ones the app never uses.
 *
 * How it works:
 *   1. After Vite writes the bundle, collect JS asset contents as "content"
 *      for PurgeCSS to scan for referenced selectors.  The radix-ui chunk
 *      is excluded because it contains string literals for ALL component
 *      class names (e.g. "rt-Button", "rt-Dialog") regardless of which
 *      components the app actually imports — including it defeats purging.
 *   2. Run PurgeCSS on each CSS asset with a safelist that preserves
 *      CSS custom properties, theme tokens, and data-attribute selectors.
 *   3. Overwrite the CSS assets with the purged output.
 */

import { PurgeCSS } from "purgecss";
import { readdir, readFile, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";

/**
 * Vite plugin that purges unused CSS in production builds.
 * @returns {import('vite').Plugin}
 */
export default function purgeCSSPlugin() {
  return {
    name: "vite-plugin-purgecss",
    apply: "build",
    enforce: "post",

    async writeBundle(outputOptions) {
      const outputDir = outputOptions.dir;
      if (!outputDir) return;

      // The output directory may not exist (e.g. React Router removes
      // build/server when ssr is disabled).
      if (
        !(await stat(outputDir).catch((e) =>
          e?.code === "ENOENT" ? null : Promise.reject(e),
        ))
      )
        return;

      const entries = await readdir(outputDir, {
        withFileTypes: true,
        recursive: true,
      });

      const jsContents = [];
      const cssFiles = [];

      for (const entry of entries) {
        if (!entry.isFile()) continue;
        const fullPath = join(entry.parentPath ?? entry.path, entry.name);

        if (/\.(js|jsx|mjs)$/.test(entry.name)) {
          // Skip the radix-ui chunk: it contains string literals for every
          // component class name ("rt-Button", "rt-Dialog", …) which makes
          // PurgeCSS think they are all in use.
          if (/^radix-ui[.-]/.test(entry.name)) continue;
          jsContents.push({
            raw: await readFile(fullPath, "utf-8"),
            extension: "js",
          });
        } else if (/\.css$/.test(entry.name)) {
          cssFiles.push(fullPath);
        }
      }

      if (cssFiles.length === 0 || jsContents.length === 0) return;

      for (const cssPath of cssFiles) {
        const originalCSS = await readFile(cssPath, "utf-8");
        // Skip tiny files -- not worth purging.
        if (originalCSS.length < 4096) continue;

        const result = await new PurgeCSS().purge({
          content: jsContents,
          css: [{ raw: originalCSS }],
          safelist: {
            standard: [
              // Radix Themes root and theme classes
              /^\.radix-themes$/,
              /^\.light/,
              /^\.dark/,
              // Keep the Reflex base layer reset styles
              /^html$/,
              /^body$/,
              /^\*$/,
            ],
            // Deep patterns: keep entire rule blocks when selector matches
            deep: [
              // CSS custom properties and tokens (--color-*, --space-*, etc.)
              /^:root$/,
              /^:where\(:root\)$/,
              /^:where\(\.radix-themes\)$/,
            ],
            // Greedy patterns: keep selector if substring matches
            greedy: [
              // Data attribute selectors used by Radix for component state
              /data-/,
            ],
          },
          variables: true,
          fontFace: true,
          keyframes: true,
          defaultExtractor: (content) => {
            return content.match(/[\w-/:]+/g) || [];
          },
        });

        if (result.length > 0 && result[0].css) {
          const purged = result[0].css;
          // Only write if we actually removed something meaningful
          if (purged.length < originalCSS.length * 0.98) {
            await writeFile(cssPath, purged);
          }
        }
      }
    },
  };
}
