import { Page, expect } from "@playwright/test";
import path from "node:path";
export async function completeAccount(page: Page) {
  await expect(
    page.locator(".sidebar, .account-profile").first(),
  ).toBeAttached();
  const profile = page.locator(".profile-onboarding .account-profile");
  if (!(await profile.count())) return;
  await profile.locator('[name="name"]').fill("وكيل تجريبي");
  await profile
    .locator('[name="description"]')
    .fill("وكيل بيع وتسويق العقارات");
  await profile.locator('[name="phone"]').fill("0555000000");
  await profile
    .locator('input[type="file"]')
    .setInputFiles(
      path.resolve(process.cwd(), "../samples/demo-generator.jpg"),
    );
  await profile.locator("button.primary").click();
  await expect(page.locator(".sidebar")).toBeAttached();
}
