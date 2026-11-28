// @vitest-environment node
import { expect, test } from "vitest";

import {
  PSEUDO_CLASSES,
  readProperties,
  readPseudoElements,
  renderCssProps,
  snakeCase,
} from "../scripts/css-props.js";

test("names a property as a Reflex user writes it", () => {
  expect(
    ["color", "backgroundColor", "WebkitFontSmoothing", "zIndex"].map(
      snakeCase,
    ),
  ).toEqual(["color", "background_color", "webkit_font_smoothing", "z_index"]);
});

test("reads what each kind of property accepts from StyleX's types", () => {
  const properties = new Map(
    readProperties().map((property) => [property.key, property]),
  );
  expect(properties.size).toBe(521);
  expect(properties.has("theme")).toBe(false);
  expect(properties.get("box_sizing")).toEqual({
    name: "boxSizing",
    key: "box_sizing",
    literals: ["border-box", "content-box", "inherit", "initial", "unset"],
    open: null,
  });
  expect(
    ["background_color", "border", "padding", "z_index", "content"].map((key) =>
      properties.get(key),
    ),
  ).toEqual([
    {
      name: "backgroundColor",
      key: "background_color",
      literals: [],
      open: "_Color",
    },
    { name: "border", key: "border", literals: [], open: "_Color" },
    { name: "padding", key: "padding", literals: [], open: "_Size" },
    { name: "zIndex", key: "z_index", literals: [], open: "_Size" },
    { name: "content", key: "content", literals: [], open: "_Str" },
  ]);
});

test("reads the pseudo-elements StyleX types", () => {
  const elements = readPseudoElements();
  expect(elements.length).toBe(33);
  expect(elements.filter((name) => !name.startsWith("-"))).toEqual([
    "after",
    "backdrop",
    "before",
    "cue",
    "cue-region",
    "file-selector-button",
    "first-letter",
    "first-line",
    "grammar-error",
    "marker",
    "placeholder",
    "selection",
    "spelling-error",
    "target-text",
  ]);
});

test("renders the types and the runtime tables", () => {
  const rendered = renderCssProps(
    [
      { name: "color", key: "color", literals: [], open: "_Color" },
      {
        name: "boxSizing",
        key: "box_sizing",
        literals: ["border-box", "content-box"],
        open: null,
      },
      {
        name: "backgroundOrigin",
        key: "background_origin",
        literals: ["border-box", "content-box"],
        open: null,
      },
    ],
    ["before"],
  );
  const typed = rendered.slice(
    rendered.indexOf("    _BoxSizing"),
    rendered.indexOf("    _Selectors"),
  );
  expect(typed).toBe(`    _BoxSizing: TypeAlias = Literal[
        "border-box",
        "content-box",
    ]

`);
  const fields = rendered.slice(
    rendered.indexOf("    class StyleProps"),
    rendered.indexOf("        _active"),
  );
  expect(fields).toBe(`    class StyleProps(_Selectors, total=False):
        """The styles of one element: CSS properties and conditional blocks of them."""

        color: _Value[_Color]
        box_sizing: _Value[_BoxSizing | _StrVar]
        background_origin: _Value[_BoxSizing | _StrVar]
        bg: _Value[_Color]
        bg_color: _Value[_Color]
        margin_x: _Value[_Size]
        margin_y: _Value[_Size]
        padding_x: _Value[_Size]
        padding_y: _Value[_Size]
`);
  expect(
    rendered.slice(
      rendered.indexOf("else:"),
      rendered.indexOf("PSEUDO_CLASSES"),
    ),
  ).toBe(`else:
    # A TypedDict of this size takes milliseconds to build, and nothing reads
    # it at runtime, where a style is a plain dict.
    StyleProps = dict

CSS_PROPS: dict[str, str] = {
    "color": "color",
    "box_sizing": "boxSizing",
    "background_origin": "backgroundOrigin",
}

`);
  expect(
    rendered.slice(rendered.indexOf("PSEUDO_ELEMENTS:")),
  ).toBe(`PSEUDO_ELEMENTS: frozenset[str] = frozenset({
    "before",
})
`);
  expect(
    rendered.slice(
      rendered.indexOf("    _Selectors"),
      rendered.indexOf("    class StyleProps"),
    ),
  ).toBe(`    _Selectors = TypedDict(
        "_Selectors",
        {
${PSEUDO_CLASSES.map((name) => `            ":${name}": "StyleProps",\n`).join("")}            "::before": "StyleProps",
        },
        total=False,
    )

`);
  expect(
    rendered.slice(
      rendered.indexOf("        _active"),
      rendered.indexOf("else:"),
    ),
  ).toBe(
    `${[...PSEUDO_CLASSES, "before"]
      .sort()
      .map((name) => `        _${name.replaceAll("-", "_")}: StyleProps\n`)
      .join("")}\n`,
  );
});
