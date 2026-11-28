// The baseline and every token, with no color scale but the black one that the
// shadows and the overlay are made of.

import * as stylex from "@stylexjs/stylex";

import.meta.glob("../../../src/tokens/*.stylex.js", { eager: true });

const styles = stylex.create({ body: { margin: 0 } });

// A list the compiler cannot see through, so that every entry has the runtime
// of StyleX and they differ by their styles alone.
const applied = [styles.body];

document.body.className = stylex.props(applied).className ?? "";
