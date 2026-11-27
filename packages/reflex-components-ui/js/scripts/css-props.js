// Renders `style/_css_props.py`: the CSS properties an rx.ui style accepts and
// the values each one takes, read from the type definitions of the pinned
// `@stylexjs/stylex` package.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import ts from "typescript";

const TYPES_DIR = fileURLToPath(
  new URL("../node_modules/@stylexjs/stylex/lib/es/types/", import.meta.url),
);

// Keys of StyleX's `CSSProperties` that are not CSS properties.
const NOT_CSS = new Set(["theme"]);

// The pseudo-classes a style can be conditioned on with an underscore key,
// such as `_hover`. StyleX types them as `:${string}`, so the list is kept
// here. Any other one, and every functional one, is written with its colon.
export const PSEUDO_CLASSES = [
  "active",
  "any-link",
  "autofill",
  "checked",
  "default",
  "disabled",
  "empty",
  "enabled",
  "first-child",
  "first-of-type",
  "focus",
  "focus-visible",
  "focus-within",
  "fullscreen",
  "hover",
  "in-range",
  "indeterminate",
  "invalid",
  "last-child",
  "last-of-type",
  "link",
  "modal",
  "only-child",
  "only-of-type",
  "open",
  "optional",
  "out-of-range",
  "placeholder-shown",
  "popover-open",
  "read-only",
  "read-write",
  "required",
  "target",
  "user-invalid",
  "user-valid",
  "valid",
  "visited",
];

// The style keys Reflex adds to CSS, and the kind of value each takes.
const REFLEX_KEYS = [
  ["bg", "_Color"],
  ["bg_color", "_Color"],
  ["margin_x", "_Size"],
  ["margin_y", "_Size"],
  ["padding_x", "_Size"],
  ["padding_y", "_Size"],
];

/**
 * What one CSS property accepts.
 *
 * @typedef {object} Property
 * @property {string} name The name StyleX gives it, such as `alignItems`.
 * @property {string} key The name a Reflex user writes, such as `align_items`.
 * @property {string[]} literals The keywords it takes, when it takes nothing
 *   else.
 * @property {"_Color" | "_Size" | "_Str" | null} open The kind of free-form
 *   value it takes, or null when only `literals` are accepted.
 */

/**
 * Convert a StyleX property name to the name a Reflex user writes.
 *
 * @param {string} name A camelCase name, capitalised when it has a vendor
 *   prefix.
 * @returns {string} The snake_case name.
 */
export function snakeCase(name) {
  return name.replace(
    /[A-Z]/g,
    (letter, index) => (index ? "_" : "") + letter.toLowerCase(),
  );
}

/**
 * Collect the names of the type aliases a type is built from.
 *
 * @param {ts.Node} node The type to walk.
 * @param {Map<string, ts.TypeNode>} aliases The aliases of the file by name.
 * @param {Set<string>} seen The names found so far, added to in place.
 */
function collectAliases(node, aliases, seen) {
  if (ts.isTypeReferenceNode(node) && ts.isIdentifier(node.typeName)) {
    const name = node.typeName.text;
    const alias = aliases.get(name);
    if (alias && !seen.has(name)) {
      seen.add(name);
      collectAliases(alias, aliases, seen);
    }
  }
  ts.forEachChild(node, (child) => collectAliases(child, aliases, seen));
}

/**
 * Read the properties of StyleX's `CSSProperties` type.
 *
 * @returns {Property[]} The properties, sorted by the key a user writes.
 */
export function readProperties() {
  const file = `${TYPES_DIR}StyleXCSSTypes.d.ts`;
  const program = ts.createProgram([file], { strict: true, noEmit: true });
  const checker = program.getTypeChecker();
  const source = program.getSourceFile(file);
  if (!source) throw new Error(`Cannot read ${file}`);

  /** @type {Map<string, ts.TypeNode>} */
  const aliases = new Map();
  for (const statement of source.statements) {
    if (ts.isTypeAliasDeclaration(statement)) {
      aliases.set(statement.name.text, statement.type);
    }
  }
  const declared = aliases.get("CSSProperties");
  if (!declared) throw new Error("StyleX no longer declares CSSProperties");

  /** @type {Property[]} */
  const properties = [];
  const type = checker.getTypeFromTypeNode(declared);
  for (const symbol of checker.getPropertiesOfType(type)) {
    const name = symbol.getName();
    if (NOT_CSS.has(name)) continue;
    const valueType = checker.getTypeOfSymbol(symbol);
    const members = valueType.isUnion() ? valueType.types : [valueType];
    /** @type {string[]} */
    const literals = [];
    let anyString = false;
    let anyNumber = false;
    for (const member of members) {
      if (member.isStringLiteral()) literals.push(member.value);
      else if (member.flags & ts.TypeFlags.String) anyString = true;
      else if (member.flags & ts.TypeFlags.NumberLike) anyNumber = true;
    }
    const used = new Set();
    for (const declaration of symbol.getDeclarations() ?? []) {
      collectAliases(declaration, aliases, used);
    }
    /** @type {Property["open"]} */
    let open = null;
    if (used.has("color")) open = "_Color";
    else if (anyNumber) open = "_Size";
    else if (anyString || literals.length === 0) open = "_Str";
    properties.push({
      name,
      key: snakeCase(name),
      literals: open ? [] : literals.sort(),
      open,
    });
  }
  return properties.sort((a, b) => (a.key < b.key ? -1 : 1));
}

/**
 * Read the pseudo-elements StyleX types.
 *
 * @returns {string[]} Their names without the colons, sorted.
 */
export function readPseudoElements() {
  const text = readFileSync(`${TYPES_DIR}StyleXTypes.d.ts`, "utf8");
  return [...text.matchAll(/^\s*'::([a-z-]+)'\??:/gm)]
    .map((match) => match[1])
    .sort();
}

/**
 * Render a python collection with one item per line, as the formatter does.
 *
 * @param {string} open The text up to and including the opening bracket.
 * @param {string[]} items The items, already rendered.
 * @param {string} close The closing bracket and what follows it.
 * @param {string} [indent] The indentation of the opening line.
 * @returns {string} The lines, ending in a newline.
 */
function block(open, items, close, indent = "") {
  return `${indent}${open}\n${items.map((item) => `${indent}    ${item},\n`).join("")}${indent}${close}\n`;
}

/**
 * Render the python module.
 *
 * @param {Property[]} properties The CSS properties.
 * @param {string[]} pseudoElements The pseudo-elements, without their colons.
 * @returns {string} The whole file.
 */
export function renderCssProps(properties, pseudoElements) {
  // Properties with the same keywords share one alias, named after the first.
  /** @type {Map<string, string>} */
  const aliasOf = new Map();
  let aliases = "";
  let fields = "";
  for (const { name, key, literals, open } of properties) {
    /** @type {string | null} */
    let value = open;
    if (!value) {
      const signature = literals.join("|");
      let alias = aliasOf.get(signature);
      if (!alias) {
        alias = `_${name[0].toUpperCase()}${name.slice(1)}`;
        aliasOf.set(signature, alias);
        aliases += `\n${block(
          `${alias}: TypeAlias = Literal[`,
          literals.map((literal) => JSON.stringify(literal)),
          "]",
          "    ",
        )}`;
      }
      value = `${alias} | _StrVar`;
    }
    fields += `        ${key}: _Value[${value}]\n`;
  }
  for (const [key, kind] of REFLEX_KEYS) {
    fields += `        ${key}: _Value[${kind}]\n`;
  }

  const plainElements = pseudoElements.filter((name) => !name.startsWith("-"));
  const underscored = [...PSEUDO_CLASSES, ...plainElements]
    .sort()
    .map((name) => `        _${name.replaceAll("-", "_")}: StyleProps\n`)
    .join("");
  const selectors = [
    ...PSEUDO_CLASSES.map((name) => `":${name}": "StyleProps"`),
    ...pseudoElements.map((name) => `"::${name}": "StyleProps"`),
  ];

  return `"""The CSS properties of an rx.ui style and the values each one takes.

Generated by js/scripts/css-props.js from the type definitions of the pinned
@stylexjs/stylex package. Do not edit: run \`npm run generate\` in js/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from typing import Any, Literal, TypeAlias, TypedDict, TypeVar

    from reflex_base.breakpoints import Breakpoints
    from reflex_base.constants.colors import Color
    from reflex_base.vars.base import Var

    _T = TypeVar("_T")

    # A value, one per breakpoint, or one per condition such as ":hover".
    _Value: TypeAlias = (
        _T | Sequence[_T] | Breakpoints[Any, Any] | Mapping[str, _T | Mapping[str, _T]]
    )
    _StrVar: TypeAlias = Var[str]
    _Str: TypeAlias = str | Var[str]
    _Size: TypeAlias = str | int | float | Var[str | int | float]
    _Color: TypeAlias = str | Color | Var[str] | Var[Color]
${aliases}
${block("_Selectors = TypedDict(", ['"_Selectors"', `{\n${selectors.map((item) => `            ${item},\n`).join("")}        }`, "total=False"], ")", "    ")}
    class StyleProps(_Selectors, total=False):
        """The styles of one element: CSS properties and conditional blocks of them."""

${fields}${underscored}
else:
    # A TypedDict of this size takes milliseconds to build, and nothing reads
    # it at runtime, where a style is a plain dict.
    StyleProps = dict

${block("CSS_PROPS: dict[str, str] = {", [...properties.map(({ key, name }) => `"${key}": "${name}"`)], "}")}
${block(
  "PSEUDO_CLASSES: frozenset[str] = frozenset({",
  PSEUDO_CLASSES.map((name) => `"${name}"`),
  "})",
)}
${block(
  "PSEUDO_ELEMENTS: frozenset[str] = frozenset({",
  pseudoElements.map((name) => `"${name}"`),
  "})",
)}`;
}

/**
 * Render `_css_props.py` from the installed StyleX package.
 *
 * @returns {string} The whole file.
 */
export function render() {
  return renderCssProps(readProperties(), readPseudoElements());
}
