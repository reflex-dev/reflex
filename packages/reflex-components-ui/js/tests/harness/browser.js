// Opens the two pages of the sweep in headless Chromium and compares what they
// read.

import { readFileSync } from "node:fs";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { chromium } from "playwright";

import { buildHarness } from "./build.js";
import { labels } from "./probe.js";

/** @typedef {import("./page.js").Config} Config */
/** @typedef {import("./page.js").Harness} Harness */
/** @typedef {"srgb" | "p3"} Gamut */

/**
 * A value the two pages disagree on, or that one of them could not read.
 *
 * @typedef {object} Difference
 * @property {Config} config The page that was shown.
 * @property {Gamut} gamut The gamut of the screen.
 * @property {string} label The custom property, or the property of the theme
 *   element.
 * @property {string} ours What the StyleX modules give.
 * @property {string} radix What @radix-ui/themes gives.
 */

const ORIGIN = "http://harness.test";
const TYPES = { html: "text/html", js: "text/javascript", css: "text/css" };
const CHUNK = 250;

/**
 * Every custom property the token stylesheet of @radix-ui/themes defines.
 *
 * @returns {string[]} Their names, in the order they first appear.
 */
export function radixCustomProperties() {
  const css = readFileSync(
    createRequire(import.meta.url).resolve("@radix-ui/themes/tokens.css"),
    "utf8",
  );
  return [
    ...new Set(
      Array.from(css.matchAll(/^\s*(--[\w-]+):/gm), ([, name]) => name),
    ),
  ];
}

/**
 * Build the two pages and open them.
 *
 * @returns {Promise<{
 *   names: string[],
 *   ours: import("playwright").Page,
 *   radix: import("playwright").Page,
 *   setGamut: (gamut: Gamut) => Promise<void>,
 *   read: (page: import("playwright").Page, config: Config) => Promise<Record<string, string>>,
 *   compare: (configs: Config[], gamut: Gamut) => Promise<{ differences: Difference[], distinct: number }>,
 *   close: () => Promise<void>,
 * }>} The pages, and what drives them.
 */
export async function openHarness() {
  const dist = await mkdtemp(join(tmpdir(), "reflex-ui-harness-"));
  await buildHarness(["ours.html", "radix.html"], dist);
  const browser = await chromium.launch();
  const context = await browser.newContext();
  await context.route(`${ORIGIN}/**`, async (route) => {
    const path = new URL(route.request().url()).pathname;
    const extension = /** @type {keyof typeof TYPES} */ (path.split(".").pop());
    await route.fulfill({
      body: await readFile(join(dist, path)),
      contentType: TYPES[extension],
    });
  });
  const names = radixCustomProperties();
  const all = labels(names);
  const pages = await Promise.all(
    ["ours", "radix"].map(async (name) => {
      const page = await context.newPage();
      page.on("pageerror", (error) => {
        throw error;
      });
      await page.goto(`${ORIGIN}/${name}.html`);
      await page.waitForFunction(() => "harness" in window);
      await page.evaluate(
        (properties) =>
          /** @type {{ harness: Harness }} */ (
            /** @type {unknown} */ (window)
          ).harness.setup(properties),
        names,
      );
      return { page, session: await context.newCDPSession(page) };
    }),
  );
  const [ours, radix] = pages.map(({ page }) => page);

  /** @type {(gamut: Gamut) => Promise<void>} */
  const setGamut = async (gamut) => {
    for (const { session } of pages) {
      await session.send("Emulation.setEmulatedMedia", {
        features: [{ name: "color-gamut", value: gamut }],
      });
    }
  };

  /**
   * Show pages in one of the two documents.
   *
   * @template {"show" | "sweep"} Method
   * @param {import("playwright").Page} page The document.
   * @param {Method} method How much to bring back.
   * @param {Parameters<Harness[Method]>[0]} argument What to show.
   * @returns {Promise<Awaited<ReturnType<Harness[Method]>>>} What was read.
   */
  const run = (page, method, argument) =>
    page.evaluate(
      ([name, value]) =>
        /** @type {any} */ (window).harness[/** @type {string} */ (name)](
          value,
        ),
      [method, argument],
    );

  return {
    names,
    ours,
    radix,
    setGamut,
    read: async (page, config) => {
      const values = await run(page, "show", config);
      return Object.fromEntries(
        all.map((label, position) => [label, values[position]]),
      );
    },
    compare: async (configs, gamut) => {
      await setGamut(gamut);
      /** @type {Difference[]} */
      const differences = [];
      const hashes = new Set();
      for (let start = 0; start < configs.length; start += CHUNK) {
        const chunk = configs.slice(start, start + CHUNK);
        const [mine, theirs] = await Promise.all([
          run(ours, "sweep", chunk),
          run(radix, "sweep", chunk),
        ]);
        for (const [index, config] of chunk.entries()) {
          hashes.add(theirs[index].hash);
          if (
            mine[index].hash === theirs[index].hash &&
            mine[index].invalid + theirs[index].invalid === 0
          ) {
            continue;
          }
          const [mineValues, theirValues] = await Promise.all([
            run(ours, "show", config),
            run(radix, "show", config),
          ]);
          for (const [position, label] of all.entries()) {
            if (
              mineValues[position] !== theirValues[position] ||
              theirValues[position].startsWith("INVALID")
            ) {
              differences.push({
                config,
                gamut,
                label,
                ours: mineValues[position],
                radix: theirValues[position],
              });
            }
          }
        }
      }
      return { differences, distinct: hashes.size };
    },
    close: async () => {
      await browser.close();
      await rm(dist, { recursive: true });
    },
  };
}
