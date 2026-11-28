// @vitest-environment node
// Each rule the package's lint enforces on `src`, shown rejecting a file that
// breaks it: a rule that is only configured can stop matching unnoticed.
import { fileURLToPath } from "node:url";

import { ESLint } from "eslint";
import { expect, test } from "vitest";

const eslint = new ESLint({
  cwd: fileURLToPath(new URL("..", import.meta.url)),
});

const NO_JSX =
  "No JSX here: the markup of an rx.ui component comes from its Python wrapper. Only tests/behaviors may render JSX.";
const NO_BARREL =
  "No barrel files: a re-export leaks the CSS of everything it names. Import from the module that defines the name.";
const VARS_EXTENSION =
  "Files that export variables from `stylex.defineVars()`, `stylex.defineConsts()`, or `stylex.defineMarker()` must end with a `.stylex.js` extension.";
const NOT_STANDARD =
  'The value "start" is not a standard CSS value for "float". Did you mean "inline-start"?';

/**
 * Lint source text as if it were the file at a path in the package.
 *
 * @param {string} filePath The path, relative to the package.
 * @param {string} code The content of the file.
 * @returns {Promise<{rule: string | null, line: number, message: string}[]>}
 *   Every problem reported, warnings included.
 */
async function lint(filePath, code) {
  const [result] = await eslint.lintText(code, { filePath });
  return result.messages.map(({ ruleId, line, message }) => ({
    rule: ruleId,
    line,
    message,
  }));
}

test("a behaviour hook that follows the rules is clean", async () => {
  const code = `import { useState } from "react";

export function useToggle() {
  return useState(false);
}
`;
  expect(await lint("src/behaviors/useToggle.js", code)).toEqual([]);
});

test.each([
  ["src/behaviors/Button.js", "an element", "<button />"],
  ["src/behaviors/Button.jsx", "an element in a .jsx file", "<button />"],
  ["src/behaviors/useMenu.js", "a fragment", "<></>"],
  ["scripts/generate.js", "an element outside src", "<button />"],
  ["tests/lint.test.js", "an element in another test", "<button />"],
])("JSX is rejected in %s (%s)", async (filePath, _name, jsx) => {
  const code = `export const rendered = () => ${jsx};\n`;
  expect(await lint(filePath, code)).toEqual([
    { rule: "no-restricted-syntax", line: 1, message: NO_JSX },
  ]);
});

test("JSX is allowed in the tests of the behaviour hooks", async () => {
  const code = "export const rendered = () => <button />;\n";
  expect(await lint("tests/behaviors/useMenu.test.jsx", code)).toEqual([]);
});

test("a component built without JSX is rejected in src", async () => {
  const code = `import React, { createElement, forwardRef } from "react";
import { createRoot } from "react-dom/client";
import { jsx } from "react/jsx-runtime";

export const Button = forwardRef(() => createElement("button"));
export const mount = [React, createRoot, jsx];
`;
  const component =
    "No React components in src: import the hooks you need by name.";
  const renders = "No React components in src: nothing here renders.";
  expect(await lint("src/behaviors/Button.js", code)).toEqual([
    {
      rule: "no-restricted-imports",
      line: 1,
      message: `'default' import from 'react' is restricted. ${component}`,
    },
    {
      rule: "no-restricted-imports",
      line: 1,
      message: `'createElement' import from 'react' is restricted. ${component}`,
    },
    {
      rule: "no-restricted-imports",
      line: 1,
      message: `'forwardRef' import from 'react' is restricted. ${component}`,
    },
    {
      rule: "no-restricted-imports",
      line: 2,
      message: `'react-dom/client' import is restricted from being used. ${renders}`,
    },
    {
      rule: "no-restricted-imports",
      line: 3,
      message: `'react/jsx-runtime' import is restricted from being used. ${renders}`,
    },
  ]);
});

test("a namespace import of react is rejected in src", async () => {
  const code = `import * as React from "react";

export const useToggle = () => React.useState(false);
`;
  expect(await lint("src/behaviors/useToggle.js", code)).toEqual([
    {
      rule: "no-restricted-imports",
      line: 1,
      message:
        "* import is invalid because 'default', 'createElement', 'cloneElement', 'forwardRef', 'memo', 'lazy', 'Component', and 'PureComponent' from 'react' are restricted. No React components in src: import the hooks you need by name.",
    },
  ]);
});

test("a barrel is rejected in src", async () => {
  const code = `export * from "./useMenu.js";
export * as slider from "./useSlider.js";
export { useListbox } from "./useListbox.js";
`;
  expect(await lint("src/behaviors/index.js", code)).toEqual([
    { rule: "no-restricted-syntax", line: 1, message: NO_BARREL },
    { rule: "no-restricted-syntax", line: 2, message: NO_BARREL },
    { rule: "no-restricted-syntax", line: 3, message: NO_BARREL },
  ]);
});

test("a re-export is allowed outside src", async () => {
  const code = 'export { generate } from "../scripts/generate.js";\n';
  expect(await lint("tests/helpers.js", code)).toEqual([]);
});

test("a rule cannot be switched off from inside a file in src", async () => {
  const code = `// eslint-disable-next-line no-restricted-syntax
export * from "./useMenu.js";
`;
  expect(await lint("src/behaviors/index.js", code)).toEqual([
    {
      rule: null,
      line: 1,
      message:
        "'// eslint-disable-next-line no-restricted-syntax' has no effect because you have 'noInlineConfig' setting in your config.",
    },
    { rule: "no-restricted-syntax", line: 2, message: NO_BARREL },
  ]);
});

test("tokens that follow the StyleX rules are clean", async () => {
  const code = `import * as stylex from "@stylexjs/stylex";

export const space = stylex.defineVars({ 1: "4px", 2: "8px" });
`;
  expect(await lint("src/tokens/space.stylex.js", code)).toEqual([]);
});

test("the StyleX rules reject invalid styles", async () => {
  const code = `import * as stylex from "@stylexjs/stylex";

const styles = stylex.create({
  root: { colr: "red", margin: "0 1px", ":hover": { color: "blue" } },
  unused: { float: "start" },
});

export const props = () => stylex.props(styles.root);
`;
  expect(await lint("src/behaviors/styles.js", code)).toEqual([
    {
      rule: "@stylexjs/valid-styles",
      line: 4,
      message: "This is not a key that is allowed by stylex",
    },
    {
      rule: "@stylexjs/valid-shorthands",
      line: 4,
      message:
        'Property shorthands using multiple values like "margin: 0 1px" are not supported in StyleX. Separate into individual properties.',
    },
    {
      rule: "@stylexjs/no-legacy-contextual-styles",
      line: 4,
      message:
        "This pseudo class syntax is deprecated. Use the new syntax specified here: https://stylexjs.com/docs/learn/styling-ui/defining-styles/#pseudo-classes",
    },
    {
      rule: "@stylexjs/valid-styles",
      line: 4,
      message:
        "Pseudo Classes, Media Queries and other At Rules should be nested as conditions within style properties. Only Pseudo Elements (::after) are allowed at the top-level",
    },
    {
      rule: "@stylexjs/no-unused",
      line: 5,
      message: "Unused style detected: styles.unused",
    },
    {
      rule: "@stylexjs/no-nonstandard-styles",
      line: 5,
      message: NOT_STANDARD,
    },
    { rule: "@stylexjs/valid-styles", line: 5, message: NOT_STANDARD },
  ]);
});

test("the StyleX rules keep variables in .stylex.js files of their own", async () => {
  const vars = `import * as stylex from "@stylexjs/stylex";

export const space = stylex.defineVars({ 1: "4px" });
`;
  expect(await lint("src/tokens/space.js", vars)).toEqual([
    { rule: "@stylexjs/enforce-extension", line: 3, message: VARS_EXTENSION },
  ]);
  expect(
    await lint("src/tokens/space.stylex.js", `${vars}export const two = 2;\n`),
  ).toEqual([
    {
      rule: "@stylexjs/enforce-extension",
      line: 4,
      message:
        "Files that export variables from `stylex.defineVars()`, `stylex.defineConsts()`, or `stylex.defineMarker()` must not export anything else.",
    },
  ]);
});
