import { Page, expect } from "@playwright/test";
// Standalone booklet fixtures must complete earlier stages before testing imports/tools.
export async function completeBookletBasics(page: Page) {
  const form = page.locator(".auction-workspace form");
  await form.locator('[name="auction_date"]').fill("2026-10-10");
  await form.locator('[name="start_time"]').fill("16:00");
  await form.locator('[name="physical_location"]').fill("الرياض");
  await form.locator("button.primary").click();
  await form.locator('[name="name"]').fill("وكيل تجريبي");
  await form.locator("button.primary").click();
  await expect(page.locator(".auction-workspace form")).toHaveCount(0);
}
