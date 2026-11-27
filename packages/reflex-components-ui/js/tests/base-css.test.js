// @vitest-environment node
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";

import { expect, test } from "vitest";

const FONT_FACE = /@font-face \{[^}]*\}/g;

/**
 * The `@font-face` rules of a stylesheet.
 *
 * @param {string | URL} path The stylesheet.
 * @returns {Promise<string[]>} The rules, as they are written.
 */
async function fontFaces(path) {
  return (await readFile(path, "utf8")).match(FONT_FACE) ?? [];
}

test("base.css has the font faces of the Radix Themes tokens", async () => {
  const require = createRequire(import.meta.url);
  const radix = await fontFaces(require.resolve("@radix-ui/themes/tokens.css"));
  expect(radix.length).toBe(20);
  expect(await fontFaces(new URL("../src/base.css", import.meta.url))).toEqual(
    radix,
  );
});
