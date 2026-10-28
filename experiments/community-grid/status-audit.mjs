import { chromium, expect } from "@playwright/test";
import fs from "node:fs";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1024, height: 768 } });
const session = await page.context().newCDPSession(page);
const results = [];
async function record(name) {
  await page.waitForTimeout(800);
  const ax = await session.send("Accessibility.getFullAXTree");
  const grid = page.locator('[role="grid"]').first();
  const value = {
    name,
    legacyLiveText: await page
      .locator(".ag-aria-description-container")
      .textContent(),
    grid: await grid.evaluate((el) => ({
      busy: el.getAttribute("aria-busy"),
      describedby: el.getAttribute("aria-describedby"),
      rowcount: el.getAttribute("aria-rowcount"),
    })),
    exposedStatusText: ax.nodes
      .filter(
        (n) =>
          !n.ignored &&
          n.role?.value === "StaticText" &&
          /No Rows To Show|Loading|Rows available|rows to show/.test(
            n.name?.value ?? "",
          ),
      )
      .map((n) => n.name.value),
  };
  results.push(value);
  return value;
}
try {
  await page.goto("http://127.0.0.1:4194/");
  await record("populated initial");
  await page
    .getByRole("button", { name: "Toggle loading", exact: true })
    .click();
  await record("loading");
  await page
    .getByRole("button", { name: "Toggle loading", exact: true })
    .click();
  await record("populated after loading");
  fs.writeFileSync(
    process.env.STATUS_EVIDENCE || "evidence/status-before.json",
    JSON.stringify(results, null, 2),
  );
  const populated = results.filter((value) =>
    value.name.startsWith("populated"),
  );
  expect(
    populated
      .flatMap((value) => value.exposedStatusText)
      .filter((text) => /No Rows To Show|Loading/.test(text)),
  ).toEqual([]);
  console.log("PASS current-status exposure");
} finally {
  await browser.close();
}
