import { chromium, expect } from "@playwright/test";
import fs from "node:fs";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
const runtimeUrl = process.env.GRID_RUNTIME_URL || "http://127.0.0.1:4192/";
const page = await browser.newPage({ viewport: { width: 1024, height: 768 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
try {
  await page.goto(runtimeUrl);
  await expect(
    page.locator('[role="columnheader"][col-id="revenue"]'),
  ).toBeVisible({ timeout: 30000 });
  const accessibleGrid = page.locator('[role="grid"]').first();
  const statusId = await accessibleGrid.getAttribute("aria-describedby");
  expect(statusId).toBeTruthy();
  await expect(accessibleGrid).toHaveAttribute("aria-busy", "false");
  await expect(page.locator(`[id="${statusId}"]`)).toHaveText(
    "Rows available.",
  );
  await page.locator(".ag-selection-checkbox input").first().check();
  await expect(page.locator("#selected")).toHaveText("a", { timeout: 10000 });
  await page.locator('[role="columnheader"][col-id="revenue"]').click();
  await expect(page.locator("#sort")).toContainText("asc", { timeout: 10000 });
  await page.locator('[role="columnheader"][col-id="revenue"]').click();
  await expect(page.locator("#sort")).toContainText("desc", { timeout: 10000 });
  await expect(
    page
      .locator('.ag-center-cols-container [row-index="0"] [col-id="revenue"]')
      .first(),
  ).toHaveText("456");
  await page.screenshot({
    path: "evidence/reflex-runtime.png",
    fullPage: true,
  });
  fs.writeFileSync(
    "evidence/reflex-runtime.json",
    JSON.stringify(
      {
        url: runtimeUrl,
        selected: await page.locator("#selected").innerText(),
        sort: await page.locator("#sort").innerText(),
        status: await page.locator(`[id="${statusId}"]`).innerText(),
        errors,
      },
      null,
      2,
    ),
  );
  expect(errors).toEqual([]);
  console.log(
    "PASS: Actual Reflex runtime rendered grid, received selected ID a and descending sort state through Python handlers.",
  );
} finally {
  await browser.close();
}
