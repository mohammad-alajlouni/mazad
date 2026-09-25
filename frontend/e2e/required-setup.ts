import { Page, expect } from "@playwright/test";

// Booklet flows are entered page by page. A field on another page is opened
// the way a requirement link opens it, then filled.
export async function fillPages(page: Page, values: Record<string, string>) {
  const form = page.locator(".auction-workspace form");
  for (const [name, value] of Object.entries(values)) {
    const field = form.locator(`[name="${name}"]`);
    await field.evaluate((el) =>
      el.dispatchEvent(new Event("reveal", { bubbles: true })),
    );
    await expect(field).toBeVisible();
    if ((await field.evaluate((el) => el.tagName)) === "SELECT")
      await field.selectOption(value);
    else await field.fill(value);
  }
}

// "Save and next" through the remaining pages until the step is saved.
export async function finishPages(page: Page) {
  const form = page.locator(".auction-workspace form");
  const current = form.locator('.page-parts [aria-current="step"]');
  for (let i = 0; i < 8 && (await form.count()); i++) {
    const before = await current.textContent();
    await form.locator(".page-part-actions button.primary").click();
    await expect
      .poll(
        async () =>
          (await form.count()) === 0 ||
          (await current.textContent()) !== before,
      )
      .toBeTruthy();
  }
  await expect(form).toHaveCount(0);
}

// The closing pages (participation steps, contact) come after the photographs.
export async function completeClosing(
  page: Page,
  values: Record<string, string> = {},
) {
  await page
    .locator(".workflow-steps")
    .getByRole("button", { name: /Closing pages|الصفحات الختامية/ })
    .click();
  await fillPages(page, values);
  await finishPages(page);
}

// Standalone booklet fixtures must complete earlier stages before testing imports/tools.
export async function completeBookletBasics(page: Page) {
  await fillPages(page, {
    auction_date: "2026-10-10",
    start_time: "16:00",
    physical_location: "الرياض",
  });
  await finishPages(page);
}
