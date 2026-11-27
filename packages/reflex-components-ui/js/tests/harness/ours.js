// The page under test: the StyleX modules of `src`, applied the way the python
// side applies them. Nothing here is specific to the root: a nested theme is
// the same classes on another element.

import { getMatchingGrayColor } from "@radix-ui/themes/helpers";
import * as stylex from "@stylexjs/stylex";

import { focusScope } from "../../src/themes/focus.js";
import * as panels from "../../src/themes/panel.js";
import * as radii from "../../src/themes/radius.js";
import * as scalings from "../../src/themes/scaling.js";
import * as scopes from "../../src/themes/scope.js";
import { theme as styles } from "../../src/themes/theme.js";
import { install } from "./page.js";

/** @typedef {import("@stylexjs/stylex").Theme<any>} StyleXTheme */

/**
 * The themes of a directory with one module for each.
 *
 * @param {Record<string, Record<string, StyleXTheme>>} modules What
 *   `import.meta.glob` found.
 * @returns {Record<string, StyleXTheme>} The theme of each module, by the name
 *   of its file.
 */
function byName(modules) {
  return Object.fromEntries(
    Object.entries(modules).map(([path, module]) => [
      path.replace(/^.*\/|\.js$/g, ""),
      Object.values(module)[0],
    ]),
  );
}

// Every scale and every token is on the page, as the sweep reads them all. An
// app only has the ones something imports.
import.meta.glob("../../src/{colors,tokens}/*.stylex.js", { eager: true });

const accents = byName(
  import.meta.glob("../../src/themes/accent/*.js", { eager: true }),
);
const grays = byName(
  import.meta.glob("../../src/themes/gray/*.js", { eager: true }),
);

/**
 * The export of a module with a theme for each value of a prop.
 *
 * @param {Record<string, StyleXTheme>} module The module.
 * @param {string} prefix What its exports start with.
 * @param {string | undefined} value The value of the prop.
 * @returns {StyleXTheme | undefined} The theme, when the prop is set.
 */
function member(module, prefix, value) {
  if (value === undefined) return undefined;
  const word = value.replace(/\W/g, "");
  return module[prefix + word[0].toUpperCase() + word.slice(1)];
}

/**
 * The classes of a theme element.
 *
 * @param {import("./page.js").ThemeProps} props What the theme sets. A prop
 *   that is left out is inherited.
 * @returns {string} The class names.
 */
function themeClass(props) {
  const { accentColor, hasBackground, appearance } = props;
  const grayColor =
    props.grayColor === "auto"
      ? getMatchingGrayColor(/** @type {any} */ (accentColor))
      : props.grayColor;
  return /** @type {string} */ (
    stylex.props(
      Object.values(scopes),
      focusScope,
      accentColor ? accents[accentColor] : null,
      grayColor ? grays[grayColor] : null,
      member(radii, "radius", props.radius),
      member(scalings, "scaling", props.scaling),
      member(panels, "panel", props.panelBackground),
      styles.root,
      hasBackground && styles.background,
      appearance && styles[appearance],
    ).className
  );
}

const root = document.body.appendChild(document.createElement("div"));
const inner = document.createElement("div");

install(({ theme, nested }) => {
  root.className = themeClass(theme);
  if (nested) {
    inner.className = themeClass(nested);
    root.append(inner);
    return inner;
  }
  inner.remove();
  return root;
});
