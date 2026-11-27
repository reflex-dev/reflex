// The whole token sweep, `npm run sweep`: every custom property Radix Themes
// defines, in every combination of accent, gray, appearance, radius and
// scaling, read under the StyleX modules and under @radix-ui/themes, on an sRGB
// screen and on a display-P3 one. `npm test` runs part of it.

import { openHarness } from "./browser.js";
import { fullSweep } from "./configs.js";

const start = Date.now();
const harness = await openHarness();
const configs = fullSweep();
let failed = false;
for (const gamut of /** @type {const} */ (["srgb", "p3"])) {
  const { differences, distinct } = await harness.compare(configs, gamut);
  console.log(
    `${gamut}: ${configs.length} themes x ${harness.names.length} custom properties, ${distinct} distinct results, ${differences.length} differences`,
  );
  for (const { config, label, ours, radix } of differences.slice(0, 50)) {
    console.log(
      `  ${label} in ${JSON.stringify(config)}\n    ours:  ${ours}\n    radix: ${radix}`,
    );
  }
  failed ||= differences.length > 0;
}
await harness.close();
console.log(`${((Date.now() - start) / 1000).toFixed(1)}s`);
process.exit(failed ? 1 : 0);
