// The whole theme and the other twenty-five accents, which is what an accent
// bound to state costs.

import * as stylex from "@stylexjs/stylex";

import { accentIndigo } from "../../../src/themes/accent/indigo.js";
import { focusScope } from "../../../src/themes/focus.js";
import { graySlate } from "../../../src/themes/gray/slate.js";
import { panelTranslucent } from "../../../src/themes/panel.js";
import { radiusMedium } from "../../../src/themes/radius.js";
import { scaling100 } from "../../../src/themes/scaling.js";
import * as scopes from "../../../src/themes/scope.js";
import { theme } from "../../../src/themes/theme.js";

import.meta.glob("../../../src/tokens/*.stylex.js", { eager: true });
import.meta.glob("../../../src/themes/accent/*.js", { eager: true });

const styles = stylex.create({ body: { margin: 0 } });

const applied = [
  styles.body,
  ...Object.values(scopes),
  focusScope,
  accentIndigo,
  graySlate,
  radiusMedium,
  scaling100,
  panelTranslucent,
  theme.root,
  theme.background,
];

document.body.className = stylex.props(applied).className ?? "";
