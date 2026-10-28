import { chromium, expect } from "@playwright/test";
import fs from "node:fs";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox"],
});
const results = [];
try {
  for (const width of [1366, 1024]) {
    const page = await browser.newPage({ viewport: { width, height: 360 } });
    await page.goto("http://127.0.0.1:4191/compact.html");
    await expect(page.locator(".ag-paging-panel")).toBeVisible();
    const footer = await page.locator(".ag-paging-panel").boundingBox();
    expect(footer.y + footer.height).toBeLessThanOrEqual(360);
    await expect(
      page.locator('.ag-center-cols-container [row-index="4"] [col-id="name"]'),
    ).toBeInViewport({ ratio: 1 });
    await page.locator('[role="columnheader"][col-id="revenue"]').click();
    await page.locator('[role="columnheader"][col-id="revenue"]').click();
    await expect(
      page.locator(
        '.ag-center-cols-container [row-index="0"] [col-id="revenue"]',
      ),
    ).toHaveText("98897");
    await page.getByLabel("Region Filter Input", { exact: true }).fill("North");
    await expect(page.locator(".ag-paging-row-summary-panel")).toContainText(
      "25",
    );
    await page.screenshot({
      path: `evidence/compact-${width}.png`,
      fullPage: true,
    });
    results.push({
      width,
      height: 360,
      pageSize: 5,
      footerBottom: footer.y + footer.height,
      sortAndFilter: true,
    });
    await page.close();
  }
  fs.writeFileSync(
    "evidence/compact-layout.json",
    JSON.stringify(results, null, 2),
  );
  console.log(
    "PASS: compact actual grid pager and all5rows bounded at1366/1024×360; sorting/filtering work.",
  );
} finally {
  await browser.close();
}
