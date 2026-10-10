import { newProject, usePhoto } from "./required-setup";
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
test("missing requirements are listed per step and lead to their fields", async ({
  page,
}) => {
  await page.goto("/");
  await page.locator(".language-switcher").selectOption("en");
  await page.getByLabel("Email address").fill(env.ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await completeAccount(page);
  const name = "Requirements " + Date.now();
  await newProject(page, name, "project");
  await expect(
    page.getByRole("navigation", { name: "Project sections" }),
  ).toBeVisible();
  const p = (
    await page.request.get("/api/projects").then((r) => r.json())
  ).find((x: { name: string }) => x.name === name);
  // Complete auction data; one property without its district; no images yet.
  expect(
    (
      await page.request.put("/api/projects/" + p.id, {
        data: {
          ...p,
          auction: {
            ...p.auction,
            auction_name: "مزاد المتطلبات",
            auction_date: "2026-10-10",
            start_time: "16:00",
            physical_location: "الرياض",
            license_number: "420000053",
            auction_contact_number: "0555000000",
            legal_announcement_text: "إعلان تجريبي للمعاينة فقط",
            booklet_url: "https://example.com/booklet/demo",
          },
        },
      })
    ).ok(),
  ).toBeTruthy();
  const item = await page.request
    .post("/api/projects/" + p.id + "/items", {
      data: {
        title: "عقار الاختبار",
        property_data: {
          property_type: "أرض",
          city: "الرياض",
          area: "1200",
          deed_number: "0011",
          plan_number: "05",
          plot_number: "1",
          usage: "سكني",
          execution_request_number: "12345",
        },
      },
    })
    .then((r) => r.json());
  await page.reload();
  await page
    .locator(".sidebar")
    .getByRole("button", { name: /My projects/ })
    .click();
  await page.getByText(name, { exact: true }).click();

  // The properties step shows what it needs; the item opens at its field.
  const steps = page.locator(".workflow-steps button");
  await steps.nth(1).click();
  const checklist = page.locator(".step-checklist");
  await expect(checklist).toContainText("District");
  await checklist.getByRole("button", { name: /District/ }).click();
  const district = page.locator('[name="property.district"]');
  await expect(district).toBeFocused();
  await district.fill("النرجس");

  // The property also needs its photograph: there is no separate images
  // step, the link opens the property at its photograph box.
  await expect(steps).toHaveCount(4);
  await expect(checklist).toContainText("Main property image");
  await expect(checklist).not.toContainText("Auction logo");
  await expect(steps.nth(1).locator(".step-missing")).toBeVisible();
  const card = page.locator(".property-cards li").filter({
    hasText: "عقار الاختبار",
  });
  await expect(card.locator(".property-thumb.empty")).toBeVisible();
  await checklist.getByRole("button", { name: /Main property image/ }).click();
  const mainBox = page.locator('.property-form [data-slot="main"]');
  await expect(mainBox).toBeFocused();
  const frame = page.frameLocator(
    '.live-preview-paper iframe[aria-hidden="false"]',
  );
  await mainBox
    .locator('input[type="file"]')
    .setInputFiles(path.join(root, "samples/demo-generator.jpg"));
  await usePhoto(page);
  // The picked photograph shows on the property's page before it is saved.
  await expect(mainBox).toContainText("Saved with the property");
  await expect(frame.locator('image[href^="data:image/"]')).toHaveCount(1);
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(card.locator("img.property-thumb")).toBeVisible();
  expect(item.id).toBeTruthy();
  await expect(page.locator(".step-checklist")).toContainText(
    "This step is complete",
  );
});
