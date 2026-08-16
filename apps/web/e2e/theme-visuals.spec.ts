import { expect, test } from "@playwright/test";

const NEW_THEMES = [
  "zariman-residuum",
  "vallis-survey",
  "deimos-twinlight",
  "sentient-eclipse",
] as const;

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("thesos.intro-seen", "true");
    localStorage.removeItem("thesos.conversations.v1");
  });
});

test("new theme scenes animate and keep the primary surface in frame", async ({ page }, testInfo) => {
  await page.goto("/");

  for (const themeId of NEW_THEMES) {
    await page.evaluate((nextTheme) => localStorage.setItem("thesos.theme.v1", nextTheme), themeId);
    await page.reload();

    await expect(page.locator("html")).toHaveAttribute("data-theme", themeId);
    const canvas = page.locator("canvas.archive-scene");
    await expect(canvas).toBeVisible();

    const firstFrame = await canvas.screenshot();
    await page.waitForTimeout(550);
    const secondFrame = await canvas.screenshot();
    expect(firstFrame.byteLength).toBeGreaterThan(3_000);
    expect(firstFrame.equals(secondFrame)).toBe(false);

    const fit = await page.evaluate(() => {
      const composer = document.querySelector(".composer-shell")?.getBoundingClientRect();
      const workspace = document.querySelector(".workspace")?.getBoundingClientRect();
      return {
        composer: composer
          ? { top: composer.top, right: composer.right, bottom: composer.bottom, left: composer.left }
          : null,
        workspace: workspace
          ? { top: workspace.top, right: workspace.right, bottom: workspace.bottom, left: workspace.left }
          : null,
        viewport: { width: window.innerWidth, height: window.innerHeight },
        overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        overflowY: document.documentElement.scrollHeight > document.documentElement.clientHeight,
      };
    });

    expect(fit.composer).not.toBeNull();
    expect(fit.workspace).not.toBeNull();
    expect(fit.composer?.left).toBeGreaterThanOrEqual(0);
    expect(fit.composer?.right).toBeLessThanOrEqual(fit.viewport.width);
    expect(fit.composer?.bottom).toBeLessThanOrEqual(fit.viewport.height);
    expect(fit.workspace?.right).toBeLessThanOrEqual(fit.viewport.width);
    expect(fit.workspace?.bottom).toBeLessThanOrEqual(fit.viewport.height);
    expect(fit.overflowX).toBe(false);
    expect(fit.overflowY).toBe(false);

    await page.screenshot({
      path: testInfo.outputPath(`${themeId}.png`),
      animations: "allow",
    });
  }

  const openMenu = page.getByRole("button", { name: "Open menu" });
  if (await openMenu.isVisible()) await openMenu.click();
  await page.getByRole("button", { name: "Theme", exact: true }).click();
  await page.waitForTimeout(250);
  const picker = page.getByRole("dialog", { name: "Interface theme" });
  await expect(picker).toBeVisible();
  await expect(picker.getByRole("button")).toHaveCount(8);
  const pickerBounds = await picker.boundingBox();
  const viewport = page.viewportSize();
  expect(pickerBounds).not.toBeNull();
  expect(viewport).not.toBeNull();
  expect(pickerBounds?.x).toBeGreaterThanOrEqual(0);
  expect(pickerBounds?.y).toBeGreaterThanOrEqual(0);
  expect((pickerBounds?.x ?? 0) + (pickerBounds?.width ?? 0)).toBeLessThanOrEqual(
    viewport?.width ?? 0,
  );
  expect((pickerBounds?.y ?? 0) + (pickerBounds?.height ?? 0)).toBeLessThanOrEqual(
    viewport?.height ?? 0,
  );
  await page.screenshot({ path: testInfo.outputPath("theme-picker.png") });
});
