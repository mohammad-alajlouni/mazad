import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
const root = path.resolve(process.cwd(), "..");
const env = Object.fromEntries(
  fs
    .readFileSync(path.join(root, ".env"), "utf8")
    .split("\n")
    .filter((l) => l.includes("=") && !l.startsWith("#"))
    .map((l) => {
      const i = l.indexOf("=");
      return [l.slice(0, i), l.slice(i + 1)];
    }),
);
test("social campaign validates media, exports exact pixels and remains separate", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.locator(".language-switcher").selectOption("en");
  await page.getByLabel("Email address").fill(env.ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await page
    .locator(".sidebar")
    .getByRole("button", { name: "Social posts", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Create social campaign", exact: true })
    .click();
  const name = "Social browser " + Date.now();
  await page.getByLabel("Social campaign name").fill(name);
  await page.getByLabel("Campaign reference").fill("SOC-" + Date.now());
  await page
    .getByRole("button", { name: "Create social campaign", exact: true })
    .click();
  await expect(page.locator(".banner-template-card")).toHaveCount(3);
  await page
    .getByLabel("Marketing headline", { exact: true })
    .fill("فرص عقارية مميزة");
  await page.getByLabel("Additional marketing line").fill("في وجهة واعدة");
  await page
    .getByLabel("Additional companion text (optional)")
    .fill("بيانات تجريبية فقط");
  await page.getByRole("button", { name: "Save design and continue" }).click();
  const form = page.locator(".auction-workspace form");
  for (const [field, value] of Object.entries({
    license_number: "420000053",
    auction_contact_number: "0555000000",
    auction_date: "2026-10-10",
    start_time: "16:00",
    physical_location: "الرياض",
    legal_announcement_text: "إعلان تجريبي للمعاينة فقط",
  }))
    await form.locator(`[name="${field}"]`).fill(value);
  await page.getByRole("button", { name: "Save auction and continue" }).click();
  await page.getByRole("button", { name: "Add property", exact: true }).click();
  await page.getByLabel("Item title").fill("عقار المنشور التجريبي");
  for (const [field, value] of Object.entries({
    property_type: "أرض سكنية",
    city: "الرياض",
    district: "النرجس",
    area: "1200",
    deed_number: "001234",
  }))
    await page.locator(`[name="property.${field}"]`).fill(value);
  await page.getByRole("button", { name: "Save item", exact: true }).click();
  await page
    .locator(".workflow-steps")
    .getByRole("button", { name: /Review and generate/ })
    .click();
  await expect(
    page.getByRole("button", { name: "Generate social posts", exact: true }),
  ).toBeDisabled();
  await expect(
    page
      .locator(".banner-missing")
      .filter({ hasText: "Auction announcement photo" }),
  ).toBeVisible();
  await page
    .locator(".workflow-steps")
    .getByRole("button", { name: /Photos and logos/ })
    .click();
  await page.getByLabel("Name", { exact: true }).fill("وكيل تجريبي");
  await page
    .locator(".auction-workspace input[type=file]")
    .setInputFiles(path.join(root, "samples/demo-generator.jpg"));
  await page
    .getByRole("button", { name: "Save selling agent", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Saved");
  for (const category of ["auction_logo", "cover"]) {
    await page.getByLabel("Image category").selectOption(category);
    await page
      .getByLabel("Image", { exact: true })
      .setInputFiles(path.join(root, "samples/demo-generator.jpg"));
    await page
      .getByRole("button", { name: "Upload image", exact: true })
      .click();
    await expect(page.getByAltText("Uploaded project asset")).toHaveCount(
      category === "cover" ? 3 : 2,
    );
  }
  await page
    .locator(".workflow-steps")
    .getByRole("button", { name: /Review and generate/ })
    .click();
  await expect(
    page.getByRole("button", { name: "Generate social posts", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Generate social posts", exact: true })
    .click();
  await expect(
    page.getByText("Actual dimensions per image: 1080 × 1080 pixels."),
  ).toBeVisible();
  await expect(page.locator(".social-caption")).toContainText("420000053");
  await expect(
    page.getByText("Technical size and text-bound checks passed", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(page.getByLabel("Editable content")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Approve output", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("approved");
  const png = page.getByRole("link", { name: /Download post/ });
  await expect(png).toHaveCount(1);
  const r = await page.request.get((await png.getAttribute("href"))!);
  expect(r.status()).toBe(200);
  const b = await r.body();
  expect([b.readUInt32BE(16), b.readUInt32BE(20)]).toEqual([1080, 1080]);
  await page
    .getByRole("button", { name: "← Back to workspace", exact: true })
    .click();
  await page
    .locator(".sidebar")
    .getByRole("button", { name: /My booklets/ })
    .click();
  await expect(page.getByText(name, { exact: true })).toHaveCount(0);
  await page
    .locator(".sidebar")
    .getByRole("button", { name: "Banners", exact: true })
    .click();
  await expect(page.getByText(name, { exact: true })).toHaveCount(0);
  await page
    .locator(".sidebar")
    .getByRole("button", { name: "Social posts", exact: true })
    .click();
  await page.getByText(name, { exact: true }).click();
  await page.locator(".language-switcher").selectOption("ar");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.screenshot({
    path: path.join(root, "output/social-workspace-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});
