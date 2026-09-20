import { completeAccount } from "./account-setup";
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
for (const kind of ["physical", "electronic", "hybrid"] as const) {
  test(`${kind} fields and required gates cannot be skipped`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/");
    await page.locator(".language-switcher").selectOption("en");
    await page.getByLabel("Email address").fill(env.ADMIN_EMAIL);
    await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Sign in to workspace" }).click();
    await completeAccount(page);
    await page
      .locator(".sidebar")
      .getByRole("button", { name: "Create project", exact: true })
      .click();
    await page
      .getByLabel("Project / auction name", { exact: true })
      .fill("Type " + kind);
    await page.getByLabel("Reference code").fill(kind + Date.now());
    await page
      .locator("form")
      .getByRole("button", { name: "Create project" })
      .click();
    const form = page.locator(".auction-workspace form");
    await form.locator('[name="auction_type"]').selectOption(kind);
    await expect(form.locator('[name="auction_date"]')).toHaveCount(
      kind === "physical" ? 1 : 0,
    );
    await expect(form.locator('[name="electronic_platform_url"]')).toHaveCount(
      kind === "physical" ? 0 : 1,
    );
    await expect(form.locator('[name="physical_location"]')).toHaveCount(
      kind === "electronic" ? 0 : 1,
    );
    await page
      .locator(".workflow-navigation")
      .getByRole("button", { name: "Next", exact: true })
      .click();
    await expect(form.locator('[name="license_number"]')).toBeVisible();
    expect(
      await form
        .locator('[name="license_number"]')
        .evaluate((el: HTMLInputElement) => el.validity.valid),
    ).toBeFalsy();
    await page
      .locator(".project-sections")
      .getByRole("button", { name: "Banners", exact: true })
      .click();
    await expect(page.locator(".banner-template-grid")).toHaveCount(0);
    const values: Record<string, string> = {
      auction_name: "مزاد آفاق",
      license_number: "420000053",
      auction_contact_number: "0555000000",
      legal_announcement_text: "إعلان تجريبي فقط",
      booklet_url: "https://example.com/booklet",
      start_time: "16:00",
    };
    if (kind === "physical") {
      values.auction_date = "2026-10-10";
      values.physical_location = "الرياض";
    } else {
      values.auction_start_date = "2026-10-10";
      values.auction_end_date = "2026-10-12";
      values.end_time = "18:00";
      values.electronic_platform_name = "منصة المزادات";
      values.electronic_platform_url = "https://example.com/auction";
      if (kind === "hybrid") values.physical_location = "الرياض";
    }
    for (const [key, value] of Object.entries(values))
      await form.locator('[name="' + key + '"]').fill(value);
    await form.getByRole("button", { name: "Save auction and cover" }).click();
    await page
      .getByRole("button", { name: "Add property", exact: true })
      .click();
    await page.getByLabel("Item title").fill("عقار تجريبي");
    await page.getByRole("button", { name: "Save item", exact: true }).click();
    await expect(page.locator('[name="property.property_type"]')).toBeVisible();
    expect(
      await page
        .locator('[name="property.property_type"]')
        .evaluate((el: HTMLInputElement) => el.validity.valid),
    ).toBeFalsy();
    await page
      .locator(".workflow-steps")
      .getByRole("button", { name: /Images/ })
      .click();
    await expect(page.locator('[name="property.property_type"]')).toBeVisible();
    if (kind === "hybrid") {
      await page.locator(".language-switcher").selectOption("ar");
      await page.setViewportSize({ width: 390, height: 844 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBeTruthy();
    }
    expect(errors).toEqual([]);
  });
}
