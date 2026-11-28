// @vitest-environment node
// The wrapper names the built files after styles it reads from an internal of
// the unplugin. A version without it must stop the build, not degrade it.
import { expect, test, vi } from "vitest";

import stylex from "../src/vite-plugin-stylex.js";

vi.mock("@stylexjs/unplugin", () => ({
  default: { vite: () => ({ name: "@stylexjs/unplugin" }) },
}));

test("an unplugin that does not expose the collected styles is rejected", () => {
  expect(() => stylex("__reflex_global_styles")).toThrow(
    new Error(
      "reflex-ui: @stylexjs/unplugin no longer exposes the styles it collected (__stylexCollectCss), which the names of the built files depend on. Install the version of @stylexjs/unplugin that reflex-components-ui pins.",
    ),
  );
});
