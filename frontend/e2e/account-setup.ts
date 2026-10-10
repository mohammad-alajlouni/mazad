import { Page, expect } from "@playwright/test";
import path from "node:path";
export async function completeAccount(page: Page) {
  // Signing in and loading the workspace can take a while on a busy machine.
  await expect(page.locator(".sidebar, .account-profile").first()).toBeAttached(
    { timeout: 20000 },
  );
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
  // The logo is placed in its frame (shown whole) before it is stored.
  await page
    .locator("dialog.image-editor")
    .getByRole("button", { name: /^(Use logo|استخدام الشعار)$/ })
    .click();
  await expect(page.locator("dialog.image-editor")).toBeHidden();
  await profile.locator("button.primary").click();
  await expect(page.locator(".sidebar")).toBeAttached();
}
