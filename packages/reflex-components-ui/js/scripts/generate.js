// Writes the generated files of the package, or with `--check` fails when a
// committed one is not what its generator produces.

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { render as renderCssProps } from "./css-props.js";

/**
 * A committed file that a generator owns.
 *
 * @typedef {object} Generated
 * @property {string} path Where the file goes, relative to the python package's
 *   root (`packages/reflex-components-ui`).
 * @property {() => string | Promise<string>} render Produces the whole file.
 */

/**
 * Every generated file. A generator is added here, so that `npm run generate`
 * writes its output and the check in CI covers it.
 *
 * @type {Generated[]}
 */
export const GENERATED = [
  {
    path: "src/reflex_components_ui/style/_css_props.py",
    render: renderCssProps,
  },
];

const PACKAGE_ROOT = fileURLToPath(new URL("../../", import.meta.url));

/**
 * Write the generated files, or find the ones that have drifted.
 *
 * @param {Generated[]} generated The files to produce.
 * @param {string} root The directory their paths are relative to.
 * @param {boolean} check Compare with what is on disk instead of writing.
 * @returns {Promise<string[]>} The paths written, or with `check` the paths
 *   whose file is missing or differs from what its generator produces.
 */
export async function generate(generated, root, check) {
  const paths = [];
  for (const { path, render } of generated) {
    const target = resolve(root, path);
    const content = await render();
    if (check) {
      const current = await readFile(target, "utf8").catch(() => null);
      if (current !== content) paths.push(path);
    } else {
      await mkdir(dirname(target), { recursive: true });
      await writeFile(target, content);
      paths.push(path);
    }
  }
  return paths;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const check = process.argv.includes("--check");
  const paths = await generate(GENERATED, PACKAGE_ROOT, check);
  if (check && paths.length > 0) {
    console.error(
      `Generated files are out of date:\n${paths.map((path) => `  ${path}`).join("\n")}\nRun \`npm run generate\` and commit the result.`,
    );
    process.exit(1);
  }
  console.log(
    check
      ? `${GENERATED.length} generated files are up to date.`
      : `Wrote ${paths.length} generated files.`,
  );
}
