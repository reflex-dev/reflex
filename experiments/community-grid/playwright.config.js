import { defineConfig } from "@playwright/test";
export default defineConfig({
  testMatch: "browser.spec.js",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:4191",
    launchOptions: {
      executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
      args: ["--no-sandbox"],
    },
  },
  webServer: {
    command: "npm run dev -- --port 4191",
    url: "http://127.0.0.1:4191",
    reuseExistingServer: true,
  },
  reporter: [
    ["list"],
    ["json", { outputFile: "evidence/browser-results.json" }],
  ],
});
