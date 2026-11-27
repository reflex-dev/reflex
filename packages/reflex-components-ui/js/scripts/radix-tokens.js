// Turns the token stylesheet of @radix-ui/themes into the StyleX modules of
// `src/colors`, `src/tokens` and `src/themes`, and into the python module that
// lists them. Every custom property keeps the name and the value Radix gives
// it; what changes is where the value is decided:
//
// - Radix defines a color once under `.light` and once under `.dark`. Here it is
//   one `light-dark()` value, picked by the `color-scheme` of the element that
//   uses it, so an appearance is one CSS property and not a second stylesheet.
// - Radix repeats every derived token on each `.radix-themes` element, so that
//   `--space-1` follows the `--scaling` of the nearest theme. Here the tokens
//   are defined on `:root`, and a StyleX theme defines every variable of its
//   group again on the element it is applied to. The scope themes override
//   nothing and exist for that: they are what makes an element a theme.

import { dirname, posix } from "node:path";

import postcss from "postcss";

/**
 * The value of a custom property in each context Radix defines it for.
 *
 * @typedef {object} Token
 * @property {string} [light] In the light appearance.
 * @property {string} [dark] In the dark appearance.
 * @property {string} [p3Light] On a display-P3 screen, when it differs.
 * @property {string} [p3Dark] On a display-P3 screen, when it differs.
 */

/**
 * A value as StyleX takes it: one string, or a default with the one a
 * display-P3 screen gets.
 *
 * @typedef {string | { default: string, p3: string }} Value
 */

/**
 * What the stylesheet says, before any of it is arranged into modules.
 *
 * @typedef {object} Model
 * @property {Map<string, Token>} tokens The custom properties defined outside a
 *   theme attribute.
 * @property {Record<string, Map<string, Map<string, string>>>} themes The
 *   declarations of each value of each theme attribute, such as
 *   `themes["accent-color"].get("red")`.
 * @property {Record<string, [string, string][]>} element The properties Radix
 *   sets on a theme element itself, by the key they get in `themes/theme.js`.
 */

/**
 * What the generator needs that the stylesheet does not say.
 *
 * @typedef {object} Options
 * @property {string} version The version of Radix Themes that was read.
 * @property {{ radius: string, scaling: string, panelBackground: string, accentColor: string, grayColor: string }} defaults
 *   The props of a Radix `Theme` that is given none.
 * @property {(accent: string) => string} matchingGray The gray an accent is
 *   paired with when the gray is `auto`.
 */

/** @typedef {import("./generate.js").Generated} Generated */

const P3_SUPPORTS = "@supports (color: color(display-p3 1 1 1))";
const P3_MEDIA = "@media (color-gamut: p3)";

// The conditions a rule may sit in. Every browser with `light-dark()` has
// `color-mix()`, so the value Radix gives the ones that do is the only value.
const CONDITIONS = new Map([
  ["", false],
  ["@supports (color: color-mix(in oklab, white, black))", false],
  [`${P3_SUPPORTS} > ${P3_MEDIA}`, true],
]);

const DARK = ":is(.dark, .dark-theme)";

// The appearance a rule outside a theme attribute applies to.
const TOKEN_SELECTORS = new Map([
  [":root", "both"],
  [":root, .light, .light-theme", "light"],
  [".dark, .dark-theme", "dark"],
  [".radix-themes", "both"],
  [":where(.radix-themes)", "both"],
  [`${DARK}, ${DARK} :where(.radix-themes:not(.light, .light-theme))`, "dark"],
  ["[data-radius]", "both"],
  [
    ".radix-themes, [data-accent-color]:where(:not([data-accent-color=''], [data-accent-color='gray']))",
    "both",
  ],
]);

// The attributes a Radix `Theme` puts its props in.
const ATTRIBUTES = [
  "accent-color",
  "gray-color",
  "radius",
  "scaling",
  "panel-background",
];

const THEME_SELECTOR = new RegExp(
  `^(?:\\.radix-themes:where\\()?\\[data-(${ATTRIBUTES.join("|")})='([^']+)'\\]\\)?$`,
);

/**
 * The selector that forces an appearance on a theme element.
 *
 * @param {string} appearance `light` or `dark`.
 * @returns {string} The selector as Radix writes it.
 */
function appearanceSelector(appearance) {
  const forced = `:where(.${appearance}, .${appearance}-theme)`;
  return `.radix-themes${forced}, :root:where(:has(.radix-themes[data-is-root-theme='true']${forced}))`;
}

// The rules that style a theme element, by their key in `themes/theme.js`.
const ELEMENT_SELECTORS = new Map([
  [".radix-themes", "root"],
  [".radix-themes:where([data-has-background='true'])", "background"],
  [appearanceSelector("light"), "light"],
  [appearanceSelector("dark"), "dark"],
]);

// Rules that reach below the theme element, which a class on it cannot do. They
// belong to the stylesheet every page loads.
const GLOBAL_SELECTORS = new Set([".radix-themes ::selection"]);

// The variable groups that are not a color scale: the name they are exported
// under, their module and the custom properties they hold. The first match
// wins.
const GROUPS = /** @type {const} */ ([
  ["space", "tokens/space.stylex.js", /^--space-/],
  ["scaling", "tokens/scaling.stylex.js", /^--scaling$/],
  ["radiusFactor", "tokens/radius.stylex.js", /^--radius-(factor|full|thumb)$/],
  ["radius", "tokens/radius.stylex.js", /^--radius-/],
  ["shadow", "tokens/shadow.stylex.js", /^--shadow-/],
  ["cursor", "tokens/cursor.stylex.js", /^--cursor-/],
  [
    "panel",
    "tokens/panel.stylex.js",
    /^--(panel-solid|backdrop-filter-panel)$/,
  ],
  ["color", "tokens/color.stylex.js", /^--color-/],
  ["accent", "tokens/accent.stylex.js", /^--accent-/],
  ["focus", "tokens/focus.stylex.js", /^--focus-/],
  ["gray", "tokens/gray.stylex.js", /^--gray-/],
  [
    "typography",
    "tokens/typography.stylex.js",
    /^--(font|line-height|letter-spacing|default|heading|code|strong|em|quote|tab)-/,
  ],
]);

// The groups with tokens that read another variable, which a scope theme
// defines again on a theme element. `focus` has a module of its own, because an
// accent on a single element needs it without the rest.
const SCOPED = ["space", "radius", "typography", "shadow", "color"];

/**
 * Read the custom properties and the theme element's styles from a stylesheet.
 *
 * @param {string} css The token stylesheet of Radix Themes.
 * @returns {Model} What it defines.
 */
export function parseTokens(css) {
  /** @type {Model} */
  const model = { tokens: new Map(), themes: {}, element: {} };
  postcss.parse(css).walkRules((rule) => {
    const conditions = [];
    for (
      let parent = rule.parent;
      parent?.type === "atrule";
      parent = parent.parent
    ) {
      const atRule = /** @type {import("postcss").AtRule} */ (parent);
      conditions.unshift(`@${atRule.name} ${atRule.params}`);
    }
    const p3 = CONDITIONS.get(conditions.join(" > "));
    const selector = rule.selector.replace(/\s+/g, " ");
    if (p3 === undefined) {
      throw new Error(
        `Unknown condition on ${selector}: ${conditions.join(" > ")}`,
      );
    }
    const appearance = TOKEN_SELECTORS.get(selector);
    const theme = THEME_SELECTOR.exec(selector);
    const element = ELEMENT_SELECTORS.get(selector);
    if (!appearance && !theme && !element && !GLOBAL_SELECTORS.has(selector)) {
      throw new Error(`Unknown selector: ${selector}`);
    }
    rule.walkDecls((decl) => {
      const value = decl.value.replace(/\s+/g, " ");
      if (!decl.prop.startsWith("--")) {
        // A prefixed copy of a property the rule also sets is the work of
        // Radix's build, and StyleX takes the standard name only.
        const standard = decl.prop.replace(/^-(webkit|moz)-/, "");
        const prefixed =
          standard !== decl.prop &&
          rule.some((node) => node.type === "decl" && node.prop === standard);
        if (element && !prefixed) {
          (model.element[element] ??= []).push([decl.prop, value]);
        }
      } else if (theme) {
        const values = (model.themes[theme[1]] ??= new Map());
        let declarations = values.get(theme[2]);
        if (!declarations) values.set(theme[2], (declarations = new Map()));
        declarations.set(decl.prop, value);
      } else if (appearance) {
        let token = model.tokens.get(decl.prop);
        if (!token) model.tokens.set(decl.prop, (token = {}));
        if (appearance !== "dark") token[p3 ? "p3Light" : "light"] = value;
        if (appearance !== "light") token[p3 ? "p3Dark" : "dark"] = value;
      } else {
        throw new Error(`${decl.prop} is set by ${selector}`);
      }
    });
  });
  return model;
}

/**
 * Split a value at the separators that are not inside parentheses.
 *
 * @param {string} value The value to split.
 * @param {string} separator One character.
 * @returns {string[]} The trimmed parts.
 */
function splitTopLevel(value, separator) {
  const parts = [];
  let depth = 0;
  let start = 0;
  for (let index = 0; index < value.length; index++) {
    const character = value[index];
    if (character === "(") depth++;
    else if (character === ")") depth--;
    else if (character === separator && depth === 0) {
      parts.push(value.slice(start, index).trim());
      start = index + 1;
    }
  }
  parts.push(value.slice(start).trim());
  return parts.filter(Boolean);
}

/**
 * One value for both appearances of a color.
 *
 * @param {string} light The color in the light appearance.
 * @param {string} dark The color in the dark appearance.
 * @returns {string} The color, or a `light-dark()` of the two.
 */
export function lightDark(light, dark) {
  return light === dark ? light : `light-dark(${light}, ${dark})`;
}

/**
 * One shadow list for both appearances.
 *
 * `light-dark()` only chooses between colors, and the two appearances of a
 * Radix shadow differ in geometry too. Layers that share their geometry keep
 * it and choose their color; a layer only one appearance has is transparent in
 * the other, where it paints nothing. Both appearances keep their paint order.
 *
 * @param {string} light The `box-shadow` value of the light appearance.
 * @param {string} dark The `box-shadow` value of the dark appearance.
 * @returns {string} A `box-shadow` value that paints as `light` or as `dark`
 *   according to the color scheme.
 */
export function mergeShadows(light, dark) {
  if (light === dark) return light;
  const [lights, darks] = [light, dark].map((shadow) =>
    splitTopLevel(shadow, ",").map((layer) => {
      const parts = splitTopLevel(layer, " ");
      const color = parts.findIndex(
        (part) => part !== "inset" && !/^-?[\d.]+(px)?$/.test(part),
      );
      return {
        color: parts[color],
        geometry: parts.toSpliced(color, 1).join(" "),
      };
    }),
  );
  // The longest common subsequence of the two lists of geometries.
  const common = lights.map(() => new Array(darks.length + 1).fill(0));
  common.push(new Array(darks.length + 1).fill(0));
  for (let l = lights.length - 1; l >= 0; l--) {
    for (let d = darks.length - 1; d >= 0; d--) {
      common[l][d] =
        lights[l].geometry === darks[d].geometry
          ? common[l + 1][d + 1] + 1
          : Math.max(common[l + 1][d], common[l][d + 1]);
    }
  }
  const layers = [];
  let l = 0;
  let d = 0;
  while (l < lights.length || d < darks.length) {
    if (
      l < lights.length &&
      d < darks.length &&
      lights[l].geometry === darks[d].geometry
    ) {
      const color = lightDark(lights[l].color, darks[d++].color);
      layers.push(`${lights[l++].geometry} ${color}`);
    } else if (
      d === darks.length ||
      (l < lights.length && common[l + 1][d] >= common[l][d + 1])
    ) {
      const { geometry, color } = lights[l++];
      layers.push(`${geometry} light-dark(${color}, transparent)`);
    } else {
      const { geometry, color } = darks[d++];
      layers.push(`${geometry} light-dark(transparent, ${color})`);
    }
  }
  return layers.join(", ");
}

/**
 * The single value of a token.
 *
 * @param {string} name The custom property.
 * @param {Token} token Its value in each context.
 * @returns {Value} The value for every appearance, and the one a display-P3
 *   screen gets when Radix has one.
 */
function resolve(name, { light, dark, p3Light, p3Dark }) {
  if (light === undefined || dark === undefined) {
    throw new Error(`${name} has no value in one appearance.`);
  }
  const merge = name.startsWith("--shadow-") ? mergeShadows : lightDark;
  const value = merge(light, dark);
  if (p3Light === undefined && p3Dark === undefined) return value;
  return { default: value, p3: merge(p3Light ?? light, p3Dark ?? dark) };
}

/**
 * The name a theme is exported under.
 *
 * @param {string} prefix What the theme sets, such as `accent`.
 * @param {string} name The value of the theme prop, such as `red` or `90%`.
 * @returns {string} A javascript identifier, such as `accentRed`.
 */
function themeExport(prefix, name) {
  const word = name.replace(/\W/g, "");
  return prefix + word[0].toUpperCase() + word.slice(1);
}

/**
 * The property name StyleX takes for a CSS property.
 *
 * @param {string} property A CSS property, such as `-webkit-font-smoothing`.
 * @returns {string} Its camel case name, such as `WebkitFontSmoothing`.
 */
function camelCase(property) {
  return property.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
}

/**
 * A property of an object literal, laid out the way the repository's formatter
 * leaves it: a string that does not fit on the line of its key goes below it.
 *
 * @param {string} indent The indentation of the property.
 * @param {string} key The key, as it is written.
 * @param {string} expression The javascript of the value.
 * @returns {string} The lines of the property.
 */
function property(indent, key, expression) {
  const line = `${indent}${key}: ${expression},`;
  return line.length > 80 && expression.startsWith('"')
    ? `${indent}${key}:\n${indent}  ${expression},\n`
    : `${line}\n`;
}

/**
 * Builds the modules, remembering which module defines each custom property so
 * that a value which reads one imports it.
 */
class Modules {
  /**
   * @param {string} version The version of Radix Themes that was read.
   */
  constructor(version) {
    this.header = `// Generated by scripts/generate.js from @radix-ui/themes ${version}. Do not edit.\n`;
    /** @type {Map<string, { module: string, name: string }>} */
    this.owners = new Map();
    /** @type {Map<string, { name: string, vars: [string, Value][] }[]>} */
    this.groups = new Map();
    /** @type {Map<string, string>} */
    this.groupModules = new Map();
    /** @type {Generated[]} */
    this.files = [];
  }

  /**
   * Add a group of variables to the module that defines it.
   *
   * @param {string} module The module, relative to `src`.
   * @param {string} name The name the group is exported under.
   * @param {[string, Value][]} vars The custom properties and their values.
   */
  define(module, name, vars) {
    const groups = this.groups.get(module) ?? [];
    this.groups.set(module, groups);
    groups.push({ name, vars });
    this.groupModules.set(name, module);
    for (const [variable] of vars) this.owners.set(variable, { module, name });
  }

  /**
   * The javascript for a value, reading the variables other modules define
   * through an import, which is what makes their CSS part of the build.
   *
   * @param {string} value The CSS value.
   * @param {string} module The module the value is written in.
   * @param {Map<string, Set<string>>} imports The names to import, by module.
   * @returns {string} A string literal, a member of an imported group or a
   *   template literal of both.
   */
  expression(value, module, imports) {
    const parts = value.split(/var\((--[\w-]+)\)/);
    let foreign = false;
    for (let index = 1; index < parts.length; index += 2) {
      const owner = this.owners.get(parts[index]);
      if (!owner || owner.module === module) {
        parts[index] = `var(${parts[index]})`;
        continue;
      }
      foreign = true;
      if (!imports.has(owner.module)) imports.set(owner.module, new Set());
      /** @type {Set<string>} */ (imports.get(owner.module)).add(owner.name);
      parts[index] = `\${${owner.name}["${parts[index]}"]}`;
    }
    if (!foreign) return JSON.stringify(parts.join(""));
    if (parts.length === 3 && parts[0] === "" && parts[2] === "") {
      return parts[1].slice(2, -1);
    }
    return `\`${parts.join("")}\``;
  }

  /**
   * The properties of an object literal of variables.
   *
   * @param {[string, Value][]} vars The custom properties and their values.
   * @param {string} module The module the object is written in.
   * @param {Map<string, Set<string>>} imports The names to import, by module.
   * @param {string} [none] The expression for a level that has no value.
   * @returns {string} One property a line, indented.
   */
  properties(vars, module, imports, none = "null") {
    /** @type {(value: string) => string} */
    const expression = (value) => this.expression(value, module, imports);
    return vars
      .map(([name, value]) =>
        typeof value === "string"
          ? property("  ", `"${name}"`, expression(value))
          : `  "${name}": {\n` +
            property("    ", "default", expression(value.default)) +
            `    "${P3_SUPPORTS}": {\n` +
            property("      ", "default", none) +
            property("      ", `"${P3_MEDIA}"`, expression(value.p3)) +
            `    },\n` +
            `  },\n`,
      )
      .join("");
  }

  /**
   * Add a module to the generated files.
   *
   * @param {string} module The module, relative to `src`.
   * @param {Map<string, Set<string>>} imports The names it imports, by module.
   * @param {string[]} statements The exports of the module.
   */
  write(module, imports, statements) {
    const lines = [...imports]
      .map(([from, names]) => {
        let path = posix.relative(dirname(module), from);
        if (!path.startsWith(".")) path = `./${path}`;
        return `import { ${[...names].sort().join(", ")} } from "${path}";\n`;
      })
      .sort();
    const content = `${this.header}\nimport * as stylex from "@stylexjs/stylex";\n\n${lines.join("")}${lines.length ? "\n" : ""}${statements.join("\n")}`;
    this.files.push({ path: `js/src/${module}`, render: () => content });
  }

  /**
   * Write every module of variables that was defined.
   */
  writeGroups() {
    for (const [module, groups] of this.groups) {
      /** @type {Map<string, Set<string>>} */
      const imports = new Map();
      const statements = groups.map(
        ({ name, vars }) =>
          `export const ${name} = stylex.defineVars({\n${this.properties(vars, module, imports)}});\n`,
      );
      this.write(module, imports, statements);
    }
  }

  /**
   * Write a module of themes.
   *
   * @param {string} module The module, relative to `src`.
   * @param {[name: string, group: string, vars: [string, Value][]][]} themes
   *   The name each theme is exported under, the group of variables it
   *   overrides and the values it gives them.
   * @returns {[string, string][]} The module and the name of each theme.
   */
  writeThemes(module, themes) {
    /** @type {Map<string, Set<string>>} */
    const imports = new Map();
    let conditional = false;
    const statements = themes.map(([name, group, vars]) => {
      conditional ||= vars.some(([, value]) => typeof value !== "string");
      const from = /** @type {string} */ (this.groupModules.get(group));
      if (!imports.has(from)) imports.set(from, new Set());
      /** @type {Set<string>} */ (imports.get(from)).add(group);
      const overrides = this.properties(vars, module, imports, "NONE");
      return `export const ${name} = stylex.createTheme(${group}, {${overrides && "\n"}${overrides}});\n`;
    });
    if (conditional) {
      statements.unshift(
        "// StyleX leaves a null level out, which the type of a string token does\n// not say.\nconst NONE = /** @type {string} */ (/** @type {unknown} */ (null));\n",
      );
    }
    this.write(module, imports, statements);
    return themes.map(([name]) => [module, name]);
  }
}

/**
 * Order entries by their name.
 *
 * @param {[string, unknown]} a An entry.
 * @param {[string, unknown]} b Another.
 * @returns {number} Negative when `a` goes first.
 */
function byName([a], [b]) {
  return a < b ? -1 : a > b ? 1 : 0;
}

/**
 * The declarations of a value of a theme attribute.
 *
 * @param {Map<string, Map<string, string>>} values The values of the attribute.
 * @param {string} name The value.
 * @returns {Map<string, string>} What it declares.
 */
function required(values, name) {
  const declarations = values.get(name);
  if (!declarations) throw new Error(`Radix has no rule for ${name}.`);
  return declarations;
}

/**
 * A python literal, laid out the way `ruff format` leaves it.
 *
 * @param {unknown} value Strings, arrays (written as tuples) and plain objects
 *   (written as dicts).
 * @param {string} indent The indentation of the line the literal starts on.
 * @returns {string} The literal.
 */
function python(value, indent = "") {
  if (typeof value === "string") return JSON.stringify(value);
  const inner = `${indent}    `;
  if (Array.isArray(value)) {
    const flat = `(${value.map((item) => python(item)).join(", ")}${value.length === 1 ? "," : ""})`;
    if (value.every((item) => typeof item === "string") && value.length <= 2) {
      return flat;
    }
    return `(\n${value.map((item) => `${inner}${python(item, inner)},\n`).join("")}${indent})`;
  }
  const entries = Object.entries(/** @type {object} */ (value));
  return `{\n${entries.map(([key, item]) => `${inner}${JSON.stringify(key)}: ${python(item, inner)},\n`).join("")}${indent}}`;
}

/**
 * The generated files for a token stylesheet.
 *
 * @param {string} css The token stylesheet of Radix Themes.
 * @param {Options} options What the stylesheet does not say.
 * @returns {Generated[]} The StyleX modules under `js/src` and the python
 *   module that lists them.
 */
export function radixTokens(css, { version, defaults, matchingGray }) {
  const { tokens, themes, element } = parseTokens(css);
  for (const attribute of ATTRIBUTES) {
    if (!themes[attribute]) {
      throw new Error(`Radix has no rule for data-${attribute}.`);
    }
  }
  const modules = new Modules(version);
  const accents = themes["accent-color"];
  const panels = themes["panel-background"];

  // The solid panel is a space toggle: `--color-panel` has to choose between
  // two variables that follow the gray scale of the element it is used on, so
  // a theme cannot hand it either of them as a value.
  for (const [name, panel] of panels) {
    if (panel.get("--color-panel") !== `var(--color-panel-${name})`) {
      throw new Error(`The ${name} panel is not --color-panel-${name}.`);
    }
    panel.delete("--color-panel");
    panel.set("--panel-solid", name === "solid" ? " " : "initial");
  }
  /** @type {Map<string, Value>} */
  const values = new Map(
    [...tokens].map(([name, token]) => [name, resolve(name, token)]),
  );
  const defaultTheme = [
    ...required(themes.scaling, defaults.scaling),
    ...required(themes.radius, defaults.radius),
    ...required(panels, defaults.panelBackground),
    ["--color-panel-if-solid", "var(--panel-solid) var(--color-panel-solid)"],
    [
      "--color-panel",
      "var(--color-panel-if-solid, var(--color-panel-translucent))",
    ],
  ];
  for (const [name, value] of defaultTheme) values.set(name, value);

  // Radix defines its pure gray as `--gray-*` on `:root` and lets a gray theme
  // replace it. Here it is the `gray` gray theme, and no accent or gray is
  // defined outside a theme, so that an app pays for the scales it uses.
  /** @type {[string, Value][]} */
  const pureGray = [];
  for (const [name, value] of values) {
    if (GROUPS.find(([, , pattern]) => pattern.test(name))?.[0] === "gray") {
      pureGray.push([name, value]);
      values.set(name, "initial");
    }
  }
  for (const name of required(accents, defaults.accentColor).keys()) {
    values.set(name, "initial");
  }

  /** @type {Map<string, [string, Value][]>} */
  const grouped = new Map();
  /** @type {Map<string, [string, Value][]>} */
  const scales = new Map();
  for (const entry of values) {
    const group = GROUPS.find(([, , pattern]) => pattern.test(entry[0]))?.[0];
    const scale = /^--([a-z]+)-/.exec(entry[0])?.[1] ?? "";
    if (!group && !values.has(`--${scale}-a9`)) {
      throw new Error(`${entry[0]} is in no group and in no color scale.`);
    }
    const target = group ? grouped : scales;
    if (!target.has(group ?? scale)) target.set(group ?? scale, []);
    /** @type {[string, Value][]} */ (target.get(group ?? scale)).push(entry);
  }
  for (const [scale, vars] of [...scales].sort(byName)) {
    modules.define(`colors/${scale}.stylex.js`, scale, vars);
  }
  for (const [name, module] of GROUPS) {
    modules.define(module, name, grouped.get(name) ?? []);
  }
  modules.writeGroups();

  /**
   * Write one module for each value of a theme attribute.
   *
   * @param {string} attribute The attribute, such as `accent-color`.
   * @param {string} prefix What the names of its themes start with.
   * @param {string} group The group its themes override.
   * @param {(name: string) => string} module The module of a value.
   * @param {[string, [string, Value][]][]} [extra] Themes Radix has no rule for.
   * @returns {Record<string, [string, string]>} The module and the export of
   *   the theme of each value.
   */
  const themeModules = (attribute, prefix, group, module, extra = []) => {
    /** @type {Record<string, [string, string]>} */
    const written = {};
    /** @type {[string, [string, Value][]][]} */
    const all = [
      ...extra,
      ...[...themes[attribute]].map(
        ([name, vars]) =>
          /** @type {[string, [string, Value][]]} */ ([name, [...vars]]),
      ),
    ];
    /** @type {Map<string, [string, string, [string, Value][]][]>} */
    const byModule = new Map();
    for (const [name, vars] of all.sort(byName)) {
      const path = module(name);
      if (!byModule.has(path)) byModule.set(path, []);
      /** @type {[string, string, [string, Value][]][]} */ (
        byModule.get(path)
      ).push([themeExport(prefix, name), group, vars]);
      written[name] = [path, themeExport(prefix, name)];
    }
    for (const [path, list] of byModule) modules.writeThemes(path, list);
    return written;
  };

  const accentThemes = themeModules(
    "accent-color",
    "accent",
    "accent",
    (name) => `themes/accent/${name}.js`,
  );
  const grayThemes = themeModules(
    "gray-color",
    "gray",
    "gray",
    (name) => `themes/gray/${name}.js`,
    [["gray", pureGray]],
  );
  const radiusThemes = themeModules(
    "radius",
    "radius",
    "radiusFactor",
    () => "themes/radius.js",
  );
  const scalingThemes = themeModules(
    "scaling",
    "scaling",
    "scaling",
    () => "themes/scaling.js",
  );
  const panelThemes = themeModules(
    "panel-background",
    "panel",
    "panel",
    () => "themes/panel.js",
  );

  for (const [group, vars] of grouped) {
    const derived = vars.some(([, value]) =>
      (typeof value === "string" ? value : value.default).includes("var("),
    );
    if (derived && group !== "focus" && !SCOPED.includes(group)) {
      throw new Error(`${group} reads a variable and has no scope theme.`);
    }
  }
  const [focusTheme] = modules.writeThemes("themes/focus.js", [
    ["focusScope", "focus", []],
  ]);
  const scopeThemes = modules.writeThemes(
    "themes/scope.js",
    SCOPED.map((group) => [`${group}Scope`, group, []]),
  );

  /** @type {Map<string, Set<string>>} */
  const imports = new Map();
  const styles = Object.entries(element).map(
    ([key, declarations]) =>
      `  ${key}: {\n${declarations.map(([name, value]) => property("    ", camelCase(name), modules.expression(value, "themes/theme.js", imports))).join("")}  },\n`,
  );
  modules.write("themes/theme.js", imports, [
    `export const theme = stylex.create({\n${styles.join("")}});\n`,
  ]);

  /** @type {Record<string, [string, string[]]>} */
  const varGroups = {};
  for (const [module, groups] of modules.groups) {
    for (const { name, vars } of groups) {
      varGroups[name] = [module, vars.map(([variable]) => variable)];
    }
  }
  const data = [
    ["RADIX_THEMES_VERSION", "str", version],
    ["VAR_GROUPS", "dict[str, tuple[str, tuple[str, ...]]]", varGroups],
    ["ACCENT_THEMES", "dict[str, tuple[str, str]]", accentThemes],
    ["GRAY_THEMES", "dict[str, tuple[str, str]]", grayThemes],
    ["RADIUS_THEMES", "dict[str, tuple[str, str]]", radiusThemes],
    ["SCALING_THEMES", "dict[str, tuple[str, str]]", scalingThemes],
    ["PANEL_BACKGROUND_THEMES", "dict[str, tuple[str, str]]", panelThemes],
    ["SCOPE_THEMES", "tuple[tuple[str, str], ...]", scopeThemes],
    ["FOCUS_THEME", "tuple[str, str]", focusTheme],
    [
      "THEME_STYLES",
      "tuple[str, str, tuple[str, ...]]",
      ["themes/theme.js", "theme", Object.keys(element)],
    ],
    [
      "MATCHING_GRAY",
      "dict[str, str]",
      Object.fromEntries(
        Object.keys(accentThemes).map((accent) => [
          accent,
          matchingGray(accent),
        ]),
      ),
    ],
    [
      "DEFAULTS",
      "dict[str, str]",
      {
        accent_color: defaults.accentColor,
        gray_color: defaults.grayColor,
        radius: defaults.radius,
        scaling: defaults.scaling,
        panel_background: defaults.panelBackground,
      },
    ],
  ];
  modules.files.push({
    path: "src/reflex_components_ui/_radix_tokens.py",
    render: () =>
      `"""The StyleX modules generated from @radix-ui/themes, and what they define.\n\nGenerated by js/scripts/generate.js. Do not edit.\n"""\n\n${data.map(([name, type, value]) => `${name}: ${type} = ${python(value)}\n`).join("\n")}`,
  });
  return modules.files;
}
