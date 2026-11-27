// @vitest-environment node
//
// What the tokens and a theme cost a page, built the way an app builds them.

import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

import { afterAll, beforeAll, expect, test } from "vitest";

import { buildHarness } from "./harness/build.js";

const KB = 1024;

/** @type {string} */
let dist;

/** @type {Record<string, { css: number, js: string }>} */
const built = {};

beforeAll(async () => {
  dist = await mkdtemp(join(tmpdir(), "reflex-ui-size-"));
  // One build for each entry: StyleX writes one stylesheet for a build.
  for (const entry of ["baseline", "tokens", "theme", "accents"]) {
    const assets = join(dist, entry, "assets");
    await buildHarness([`size/${entry}.js`], join(dist, entry));
    const files = await readdir(assets);
    const [css, js] = await Promise.all(
      [".css", ".js"].map((extension) =>
        readFile(
          join(
            assets,
            /** @type {string} */ (
              files.find((file) => file.endsWith(extension))
            ),
          ),
        ),
      ),
    );
    built[entry] = { css: gzipSync(css).length, js: js.toString() };
  }
}, 120_000);

afterAll(async () => {
  await rm(dist, { recursive: true });
});

test("a whole theme, with one accent and one gray, is under 6 KB of gzipped CSS", () => {
  expect(built.theme.css - built.baseline.css).toBeLessThanOrEqual(6 * KB);
});

test("every accent at once, as an accent bound to state needs, is under 28 KB", () => {
  expect(built.accents.css - built.baseline.css).toBeLessThanOrEqual(28 * KB);
});

test("the tokens alone are under 2.5 KB of gzipped CSS", () => {
  expect(built.tokens.css - built.baseline.css).toBeLessThanOrEqual(2.5 * KB);
});

test("the tokens add no javascript", () => {
  expect(built.tokens.js).toBe(built.baseline.js);
});

test("a theme adds its class names to the javascript and nothing else", () => {
  // Each theme is an object of the two class names StyleX compiled it to.
  const themes = built.theme.js.match(/\{\w+:`\w+ \w+`,\$\$css:!0\}/g);
  expect(themes?.length).toBe(11);
  // An accent that is imported and not applied is not in the bundle.
  expect(built.accents.js).toBe(built.theme.js);
});
