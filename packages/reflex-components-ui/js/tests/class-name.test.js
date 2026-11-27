// @vitest-environment node
import * as stylex from "@stylexjs/stylex";
import { expect, test } from "vitest";

import { className } from "../src/class-name.js";

const red = { color: "red-class", top: "top-class", $$css: true };
const blue = { color: "blue-class", $$css: "app/routes/page.jsx:3" };
const unset = { top: null, $$css: true };

test("the class names of every style are joined", () => {
  expect(className(red)).toBe("red-class top-class");
  expect(className({ group: "theme group" }, red)).toBe(
    "theme group red-class top-class",
  );
});

test("a later style wins a property, and a falsy one is skipped", () => {
  expect(className(red, blue)).toBe("blue-class top-class");
  expect(className(blue, red)).toBe("red-class top-class");
  expect(className(red, false, null, undefined, unset)).toBe("red-class");
  expect(className()).toBe("");
});

test("the classes are the ones the StyleX runtime gives", () => {
  /** @type {any[][]} */
  const cases = [[red], [red, blue], [blue, red], [red, false, unset]];
  for (const styles of cases) {
    const expected = stylex.props(...styles).className ?? "";
    expect(className(...styles).split(" ").sort()).toEqual(
      expected.split(" ").filter(Boolean).sort(),
    );
  }
});
