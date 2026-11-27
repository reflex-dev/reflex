// @vitest-environment node
import { readdir, readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { expect, test } from "vitest";

import {
  lightDark,
  mergeShadows,
  parseTokens,
  radixTokens,
} from "../scripts/radix-tokens.js";

const FIXTURE = fileURLToPath(
  new URL("./fixtures/radix-tokens/", import.meta.url),
);

const OPTIONS = {
  version: "0.0.0",
  defaults: {
    radius: "medium",
    scaling: "100%",
    panelBackground: "translucent",
    accentColor: "red",
    grayColor: "auto",
  },
  matchingGray: (/** @type {string} */ accent) =>
    accent === "red" ? "slate" : "gray",
};

/**
 * The files below a directory.
 *
 * @param {string} directory The directory.
 * @returns {Promise<Record<string, string>>} Their content, by their path
 *   relative to the directory.
 */
async function filesBelow(directory) {
  const entries = await readdir(directory, {
    recursive: true,
    withFileTypes: true,
  });
  /** @type {Record<string, string>} */
  const files = {};
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    const path = `${entry.parentPath}/${entry.name}`;
    files[path.slice(directory.length)] = await readFile(path, "utf8");
  }
  return files;
}

/**
 * The message of the error a function throws. postcss adds the node it was
 * walking to an error, so the error itself is not compared.
 *
 * @param {() => unknown} run The function.
 * @returns {string | null} The message, or null when it does not throw.
 */
function thrown(run) {
  try {
    run();
  } catch (error) {
    return /** @type {Error} */ (error).message;
  }
  return null;
}

test("a stylesheet becomes the modules of its colors, tokens and themes", async () => {
  const css = await readFile(`${FIXTURE}tokens.css`, "utf8");
  const generated = Object.fromEntries(
    await Promise.all(
      radixTokens(css, OPTIONS).map(async ({ path, render }) => [
        path,
        await render(),
      ]),
    ),
  );
  expect(generated).toEqual(await filesBelow(`${FIXTURE}expected/`));
});

test("a color that is the same in both appearances stays as it is", () => {
  expect(lightDark("#0090ff", "#0090ff")).toBe("#0090ff");
});

test("a color that differs is chosen by the color scheme", () => {
  expect(lightDark("white", "var(--gray-1)")).toBe(
    "light-dark(white, var(--gray-1))",
  );
});

test("shadows with the same layers choose their colors", () => {
  expect(
    mergeShadows(
      "0 0 0 1px color-mix(in oklab, var(--gray-a3), var(--gray-3) 25%), 0 8px 40px var(--black-a1)",
      "0 0 0 1px color-mix(in oklab, var(--gray-a6), var(--gray-6) 25%), 0 8px 40px var(--black-a1)",
    ),
  ).toBe(
    "0 0 0 1px light-dark(color-mix(in oklab, var(--gray-a3), var(--gray-3) 25%), color-mix(in oklab, var(--gray-a6), var(--gray-6) 25%)), 0 8px 40px var(--black-a1)",
  );
});

test("a shadow layer of one appearance is transparent in the other, and both keep their order", () => {
  expect(
    mergeShadows(
      "inset 0 0 0 1px var(--gray-a5), inset 0 1.5px 2px 0 var(--gray-a2), inset 0 1.5px 2px 0 var(--black-a2)",
      "inset 0 -1px 1px 0 var(--gray-a3), inset 0 0 0 1px var(--gray-a3), inset 0 3px 4px 0 var(--black-a5), inset 0 0 0 1px var(--gray-a4)",
    ),
  ).toBe(
    [
      "inset 0 -1px 1px 0 light-dark(transparent, var(--gray-a3))",
      "inset 0 0 0 1px light-dark(var(--gray-a5), var(--gray-a3))",
      "inset 0 1.5px 2px 0 light-dark(var(--gray-a2), transparent)",
      "inset 0 1.5px 2px 0 light-dark(var(--black-a2), transparent)",
      "inset 0 3px 4px 0 light-dark(transparent, var(--black-a5))",
      "inset 0 0 0 1px light-dark(transparent, var(--gray-a4))",
    ].join(", "),
  );
});

test("identical shadows are left alone", () => {
  expect(mergeShadows("0 0 0 1px red", "0 0 0 1px red")).toBe("0 0 0 1px red");
});

test("a rule is read into the appearance and the gamut it applies to", () => {
  const { tokens, themes, element } = parseTokens(`
    :root, .light, .light-theme { --red-9: #e5484d; }
    .dark, .dark-theme { --red-9: #e5484e; }
    @supports (color: color(display-p3 1 1 1)) {
      @media (color-gamut: p3) {
        .dark, .dark-theme { --red-9: color(display-p3 0.83 0.329 0.324); }
      }
    }
    :root { --red-contrast: white; }
    [data-accent-color='red'] { --accent-9: var(--red-9); }
    .radix-themes:where([data-scaling='90%']) { --scaling: 0.9; }
    .radix-themes { --space-1:  calc(4px
      * var(--scaling)); -webkit-text-size-adjust: none; text-size-adjust: none; }
    .radix-themes ::selection { background-color: var(--focus-a5); }
  `);
  expect(Object.fromEntries(tokens)).toEqual({
    "--red-9": {
      light: "#e5484d",
      dark: "#e5484e",
      p3Dark: "color(display-p3 0.83 0.329 0.324)",
    },
    "--red-contrast": { light: "white", dark: "white" },
    "--space-1": {
      light: "calc(4px * var(--scaling))",
      dark: "calc(4px * var(--scaling))",
    },
  });
  expect(
    Object.fromEntries(
      Object.entries(themes).map(([attribute, values]) => [
        attribute,
        Object.fromEntries(
          [...values].map(([name, vars]) => [name, Object.fromEntries(vars)]),
        ),
      ]),
    ),
  ).toEqual({
    "accent-color": { red: { "--accent-9": "var(--red-9)" } },
    scaling: { "90%": { "--scaling": "0.9" } },
  });
  expect(element).toEqual({ root: [["text-size-adjust", "none"]] });
});

// A selector or a condition the generator has not seen is a change in how
// Radix builds its tokens, which it cannot translate by guessing.
test("an unknown selector is an error", () => {
  expect(thrown(() => parseTokens(".rt-Button { --accent-9: red; }"))).toBe(
    "Unknown selector: .rt-Button",
  );
});

test("an unknown condition is an error", () => {
  expect(
    thrown(() =>
      parseTokens("@media (min-width: 520px) { :root { --space-1: 4px; } }"),
    ),
  ).toBe("Unknown condition on :root: @media (min-width: 520px)");
});

test("a custom property on the selection rule is an error", () => {
  expect(
    thrown(() => parseTokens(".radix-themes ::selection { --focus-1: red; }")),
  ).toBe("--focus-1 is set by .radix-themes ::selection");
});

test("a token with one appearance is an error", async () => {
  const css = await readFile(`${FIXTURE}tokens.css`, "utf8");
  expect(
    thrown(() =>
      radixTokens(`${css}.dark, .dark-theme { --amber-9: #ffc53d; }`, OPTIONS),
    ),
  ).toBe("--amber-9 has no value in one appearance.");
});

test("a token that is in no group and in no scale is an error", async () => {
  const css = await readFile(`${FIXTURE}tokens.css`, "utf8");
  expect(
    thrown(() => radixTokens(`${css}:root { --container-1: 448px; }`, OPTIONS)),
  ).toBe("--container-1 is in no group and in no color scale.");
});

test("a stylesheet without one of the theme attributes is an error", () => {
  expect(
    thrown(() => radixTokens(":root { --red-9: #e5484d; }", OPTIONS)),
  ).toBe("Radix has no rule for data-accent-color.");
});
