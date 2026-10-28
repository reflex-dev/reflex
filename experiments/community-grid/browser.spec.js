import { test, expect } from "@playwright/test";
import fs from "node:fs";

test("Community renderer handles core interactions and saved view state", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "warning" || m.type() === "error") errors.push(m.text());
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const revenue = page.locator('.ag-center-cols-container [col-id="revenue"]');
  await expect(revenue.first()).toHaveText("0");
  const visibleRows = await page
    .locator('.ag-center-cols-container [role="row"]')
    .count();
  expect(visibleRows).toBeLessThan(100);
  await page.locator('[role="columnheader"][col-id="revenue"]').click();
  await expect
    .poll(() => page.evaluate(() => window.lastGridState?.sort?.sortModel))
    .toEqual([{ colId: "revenue", sort: "asc" }]);
  await page.locator('[role="columnheader"][col-id="revenue"]').click();
  await expect
    .poll(async () => Number(await revenue.first().innerText()))
    .toBeGreaterThan(99000);
  await page.getByLabel("Region Filter Input", { exact: true }).fill("North");
  await expect(page.locator(".ag-paging-row-summary-panel")).toContainText(
    "2,500",
  );
  await expect(
    page.locator('.ag-center-cols-container [col-id="region"]').first(),
  ).toHaveText("North");
  await page.getByLabel("Region Filter Input", { exact: true }).fill("");
  await expect(page.locator(".ag-paging-row-summary-panel")).toContainText(
    "10,000",
  );
  await page.getByLabel("Search rows", { exact: true }).fill("Account 0123");
  await expect(page.locator(".ag-paging-row-summary-panel")).toContainText(
    "1 to 2 of 2",
  );
  await expect(
    page.locator('.ag-center-cols-container [col-id="name"]', {
      hasText: "Account 0123",
    }),
  ).toBeVisible();
  await page.getByLabel("Search rows", { exact: true }).fill("");
  await page.getByRole("button", { name: "Next Page", exact: true }).click();
  await expect(page.locator(".ag-paging-description")).toContainText(
    "2 of 400",
  );
  await page
    .locator('.ag-center-cols-container [col-id="name"]')
    .first()
    .click();
  const focusedBefore = Number(
    await page
      .locator(".ag-cell-focus")
      .locator("..")
      .getAttribute("row-index"),
  );
  await page.keyboard.press("ArrowDown");
  await expect(page.locator(".ag-cell-focus")).toHaveAttribute(
    "col-id",
    "name",
  );
  await expect(page.locator(".ag-cell-focus").locator("..")).toHaveAttribute(
    "row-index",
    String(focusedBefore + 1),
  );
  await page.locator(".ag-selection-checkbox input").first().check();
  await expect
    .poll(() => page.evaluate(() => window.selectedIds?.length))
    .toBe(1);
  const header = page.locator('[role="columnheader"][col-id="name"]');
  const before = (await header.boundingBox()).width;
  const handle = await header.locator(".ag-header-cell-resize").boundingBox();
  await page.mouse.move(
    handle.x + handle.width / 2,
    handle.y + handle.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    handle.x + handle.width / 2 + 50,
    handle.y + handle.height / 2,
    { steps: 8 },
  );
  await page.mouse.up();
  await expect
    .poll(async () => (await header.boundingBox()).width)
    .toBeGreaterThan(before + 30);
  await page.getByText("Columns", { exact: true }).click();
  await page.getByLabel("Pin region", { exact: true }).selectOption("left");
  await expect(
    page.locator(
      '.ag-pinned-left-header [role="columnheader"][col-id="region"]',
    ),
  ).toBeVisible();
  await page.getByRole("checkbox", { name: "Active", exact: true }).uncheck();
  await expect(
    page.locator('[role="columnheader"][col-id="active"]'),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Move revenue earlier", exact: true })
    .click();
  await expect
    .poll(() =>
      page.evaluate(() =>
        window.lastGridState?.columnOrder?.orderedColIds.indexOf("revenue"),
      ),
    )
    .toBeLessThan(3);
  await page.getByText("Columns", { exact: true }).click();
  await page.getByLabel("Region Filter Input", { exact: true }).fill("North");
  await expect
    .poll(() =>
      page.evaluate(
        () => window.lastGridState?.filter?.filterModel?.region?.filter,
      ),
    )
    .toBe("North");
  const selectedBefore = await page.evaluate(() => window.selectedIds);
  await page
    .getByRole("button", { name: "Reverse source rows", exact: true })
    .click();
  await expect
    .poll(() => page.evaluate(() => window.lastGridState?.rowSelection))
    .toEqual(selectedBefore);
  await page.getByRole("button", { name: "Save view", exact: true }).click();
  const saved = await page.evaluate(() => window.savedGridState);
  await page
    .getByRole("button", { name: "Restore saved view", exact: true })
    .click();
  await expect(
    page.locator(
      '.ag-pinned-left-header [role="columnheader"][col-id="region"]',
    ),
  ).toBeVisible();
  await expect(
    page.locator('[role="columnheader"][col-id="active"]'),
  ).toHaveCount(0);
  await expect
    .poll(() => page.evaluate(() => window.lastGridState?.columnOrder))
    .toEqual(saved.columnOrder);
  const fixedSizing = (state) =>
    state.columnSizing.columnSizingModel.filter((col) => !col.flex);
  await expect
    .poll(() => page.evaluate(() => window.lastGridState).then(fixedSizing))
    .toEqual(fixedSizing(saved));
  await expect
    .poll(() => page.evaluate(() => window.lastGridState?.filter))
    .toEqual(saved.filter);
  await expect
    .poll(() => page.evaluate(() => window.lastGridState?.pagination))
    .toEqual(saved.pagination);
  await expect
    .poll(() => page.evaluate(() => window.lastGridState?.sort))
    .toEqual(saved.sort);
  await expect
    .poll(() => page.evaluate(() => window.lastGridState?.rowSelection))
    .toEqual(saved.rowSelection);
  await page.screenshot({
    path: "evidence/desktop-customized.png",
    fullPage: true,
  });
  fs.writeFileSync("evidence/view-state.json", JSON.stringify(saved, null, 2));
  fs.writeFileSync(
    "evidence/core-metrics.json",
    JSON.stringify(
      {
        rows: 10000,
        renderedRows: visibleRows,
        resizedFrom: before,
        resizedTo: (await header.boundingBox()).width,
        errors,
      },
      null,
      2,
    ),
  );
  expect(errors.filter((e) => !e.includes("favicon"))).toEqual([]);
});

for (const [name, width, height] of [
  ["desktop", 1440, 900],
  ["laptop", 1024, 768],
  ["mobile", 390, 844],
]) {
  test(`${name} layout, theme and loading/empty states`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await page.goto("/");
    await expect(
      page.locator('[role="columnheader"][col-id="name"]'),
    ).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBe(width);
    await page.screenshot({ path: `evidence/${name}.png`, fullPage: true });
    await page.getByText("Columns", { exact: true }).click();
    await page.screenshot({
      path: `evidence/${name}-columns.png`,
      fullPage: true,
    });
    const menu = await page.locator("details > div").boundingBox();
    expect(menu.x).toBeGreaterThanOrEqual(0);
    expect(menu.x + menu.width).toBeLessThanOrEqual(width);
    await page.getByText("Columns", { exact: true }).click();
    await page
      .getByRole("button", { name: "Toggle dark", exact: true })
      .click();
    await page.screenshot({
      path: `evidence/${name}-dark.png`,
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Toggle empty", exact: true })
      .click();
    await expect(page.locator(".ag-overlay-no-rows-center")).toBeVisible();
    await page.screenshot({
      path: `evidence/${name}-empty.png`,
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Toggle loading", exact: true })
      .click();
    await expect(page.locator(".ag-overlay-loading-center")).toBeVisible();
    await page.screenshot({
      path: `evidence/${name}-loading.png`,
      fullPage: true,
    });
  });
}

test("10k unpaginated rows remain virtualized while scrolling", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Toggle pagination", exact: true })
    .click();
  await expect(page.locator(".ag-paging-panel")).toBeHidden();
  const rendered = () =>
    page.locator('.ag-center-cols-container [role="row"]').count();
  const startCount = await rendered();
  expect(startCount).toBeLessThan(100);
  const scroll = await page.locator(".ag-body-viewport").evaluate((el) => {
    el.scrollTop = el.scrollHeight;
    return { height: el.clientHeight, scrollHeight: el.scrollHeight };
  });
  await expect(
    page.locator('.ag-center-cols-container [col-id="name"]', {
      hasText: "Account 9999",
    }),
  ).toBeVisible();
  const endCount = await rendered();
  expect(endCount).toBeLessThan(100);
  fs.writeFileSync(
    "evidence/virtualization.json",
    JSON.stringify(
      { rows: 10000, pagination: false, startCount, endCount, ...scroll },
      null,
      2,
    ),
  );
  await page.screenshot({
    path: "evidence/desktop-10k-scrolled.png",
    fullPage: true,
  });
});

test("current accessible status follows loading, empty, filtered and populated states", async ({
  page,
}) => {
  const cdp = await page.context().newCDPSession(page);
  const transitions = [];
  await page.goto("/");
  const grid = page.locator('[role="grid"]').first();
  const statusId = await grid.getAttribute("aria-describedby");
  expect(statusId).toBeTruthy();
  const status = page.locator(`[id="${statusId}"]`);
  await expect(status).toHaveAttribute("role", "status");
  await expect(status).toHaveAttribute("aria-live", "polite");
  await expect(status).toHaveAttribute("aria-atomic", "true");
  async function check(name, text, busy) {
    await expect(status).toHaveText(text);
    await expect(grid).toHaveAttribute("aria-busy", String(busy));
    await page.waitForTimeout(300);
    const ax = await cdp.send("Accessibility.getFullAXTree");
    const accessibleGrid = ax.nodes.find(
      (node) => !node.ignored && node.role?.value === "grid",
    );
    expect(accessibleGrid?.description?.value).toBe(text);
    const names = ax.nodes
      .filter((node) => !node.ignored && node.role?.value === "StaticText")
      .map((node) => node.name?.value ?? "");
    expect(names.filter((value) => value === text)).toHaveLength(1);
    expect(
      names.filter((value) => /No Rows To Show|Loading\.\.\./.test(value)),
    ).toEqual([]);
    transitions.push({
      name,
      text,
      busy,
      legacyLiveText: await page
        .locator(".ag-aria-description-container")
        .textContent(),
    });
  }
  await check("initial populated", "Rows available.", false);
  await page.getByLabel("Search rows", { exact: true }).focus();
  await page
    .getByRole("button", { name: "Toggle loading", exact: true })
    .click();
  await check("loading populated", "Loading rows.", true);
  await page
    .getByRole("button", { name: "Toggle loading", exact: true })
    .click();
  await check("loaded populated", "Rows available.", false);
  await page.getByRole("button", { name: "Toggle empty", exact: true }).click();
  await check("empty", "No rows to show.", false);
  await page
    .getByRole("button", { name: "Toggle loading", exact: true })
    .click();
  await check("loading empty", "Loading rows.", true);
  await page
    .getByRole("button", { name: "Toggle loading", exact: true })
    .click();
  await check("loaded empty", "No rows to show.", false);
  await page.getByRole("button", { name: "Toggle empty", exact: true }).click();
  await check("restored populated", "Rows available.", false);
  await page
    .getByLabel("Search rows", { exact: true })
    .fill("no-synthetic-record-matches");
  await check("filtered empty", "No rows to show.", false);
  await expect(page.getByLabel("Search rows", { exact: true })).toBeFocused();
  await page.getByLabel("Search rows", { exact: true }).fill("");
  await check("filtered populated", "Rows available.", false);
  fs.writeFileSync(
    "evidence/status-transitions.json",
    JSON.stringify(transitions, null, 2),
  );
});

for (const path of ["/?empty=1", "/?query=no-synthetic-record-matches"]) {
  test(`initial empty status is accurate at ${path}`, async ({ page }) => {
    await page.goto(path);
    const grid = page.locator('[role="grid"]').first();
    await expect(grid).toBeVisible();
    const id = await grid.getAttribute("aria-describedby");
    expect(id).toBeTruthy();
    await expect(page.locator(`[id="${id}"]`)).toHaveText("No rows to show.");
    await expect(grid).toHaveAttribute("aria-busy", "false");
    if (path.includes("empty=1")) {
      await expect(page.locator(".ag-overlay-no-rows-center")).toBeVisible();
    }
    await expect(
      page.locator('.ag-center-cols-container [role="row"]'),
    ).toHaveCount(0);
  });
}
