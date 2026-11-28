// What a page pays for StyleX before it has a token or a theme.

import * as stylex from "@stylexjs/stylex";

const styles = stylex.create({ body: { margin: 0 } });

// A list the compiler cannot see through, so that every entry has the runtime
// of StyleX and they differ by their styles alone.
const applied = [styles.body];

document.body.className = stylex.props(applied).className ?? "";
