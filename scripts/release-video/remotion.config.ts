import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setCodec("h264");
Config.setOverwriteOutput(true);
Config.setConcurrency(4);

// Reuse the Chromium already present in the environment instead of downloading
// one. It must be the headless shell: Remotion launches with old-headless flags
// that the full Chrome binary no longer accepts.
// Override with REMOTION_BROWSER_EXECUTABLE when running elsewhere.
const browser =
  process.env.REMOTION_BROWSER_EXECUTABLE ??
  "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
Config.setBrowserExecutable(browser);
