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

test("independent banner workspace validates, generates and exports", async ({
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
    .getByRole("button", { name: "Banners", exact: true })
    .click();
  await page
    .getByRole("button", {
      name: "Create standalone banner campaign",
      exact: true,
    })
    .click();
  const name = "Banner browser " + Date.now();
  await page.getByLabel("Banner campaign name").fill(name);
  await page.getByLabel("Campaign reference").fill("BAN-" + Date.now());
  await page
    .getByRole("button", { name: "Create banner campaign", exact: true })
    .click();
  await expect(page.locator(".banner-template-card")).toHaveCount(3);
  await page.locator('input[value="4x2"]').check();
  await page
    .getByRole("button", { name: "Save template and continue" })
    .click();
  const auction = page.locator(".auction-workspace form");
  for (const [field, value] of Object.entries({
    license_number: "420000053",
    auction_contact_number: "0555000000",
    auction_date: "2026-10-10",
    start_time: "16:00",
    physical_location: "الرياض",
    booklet_url: "https://example.com/booklet/browser",
    legal_announcement_text: "إعلان تجريبي للمعاينة فقط",
  }))
    await auction.locator(`[name="${field}"]`).fill(value);
  await page.getByRole("button", { name: "Save auction and continue" }).click();
  await page.getByRole("button", { name: "Add property", exact: true }).click();
  await page.getByLabel("Item title").fill("عقار البنر التجريبي");
  for (const [field, value] of Object.entries({
    property_type: "أرض سكنية",
    city: "الرياض",
    district: "النرجس",
    usage: "سكني",
    area: "1200",
    deed_number: "001234",
    plan_number: "05",
    plot_number: "12",
  }))
    await page.locator(`[name="property.${field}"]`).fill(value);
  await page.getByRole("button", { name: "Save item", exact: true }).click();
  await expect(
    page.locator('[name="property.execution_request_number"]'),
  ).toBeVisible();
  expect(
    await page
      .locator('[name="property.execution_request_number"]')
      .evaluate((e: HTMLInputElement) => e.validity.valid),
  ).toBeFalsy();
  await page
    .locator('[name="property.execution_request_number"]')
    .fill("987654321");
  await page.getByRole("button", { name: "Save item", exact: true }).click();
  await page
    .locator(".workflow-steps")
    .getByRole("button", { name: /Photos and logos/ })
    .click();
  // The auction icon is fixed by the identity; no logo upload is needed.
  await page
    .locator(".workflow-steps")
    .getByRole("button", { name: /Review and generate/ })
    .click();
  await expect(
    page.getByRole("button", { name: "Generate banners", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Generate banners", exact: true })
    .click();
  await expect(page.locator(".review h1")).toHaveText("Banners");
  await expect(
    page.getByText("Listed sizes are final dimensions", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save changes", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Approve output", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("approved");
  const links = page.locator('a[href*="download=true"]');
  await expect(links).toHaveCount(2);
  const response = await page.request.get(
    (await links.first().getAttribute("href"))!,
  );
  expect(response.status()).toBe(200);
  await page
    .getByRole("button", { name: "← Back to workspace", exact: true })
    .click();
  await page
    .locator(".sidebar")
    .getByRole("button", { name: /My projects/ })
    .click();
  await expect(page.getByText(name, { exact: true })).toHaveCount(0);
  await page
    .locator(".sidebar")
    .getByRole("button", { name: "Banners", exact: true })
    .click();
  await expect(page.getByText(name, { exact: true })).toBeVisible();
  await page.getByText(name, { exact: true }).click();
  await page.locator(".language-switcher").selectOption("ar");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.screenshot({
    path: path.join(root, "output/banner-workspace-mobile.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});
