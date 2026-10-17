import { completeAccount } from "./account-setup";
import { newProject } from "./required-setup";
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
test("a property takes up to eight deeds, listed under one label on its booklet page", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/#login");
  await page.locator(".language-switcher").selectOption("en");
  await page.getByLabel("Email address").fill(env.ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await completeAccount(page);
  const project = await newProject(
    page,
    "Deeds " + Date.now(),
    "booklet",
    {},
    {
      auction_date: "2026-10-10",
      start_time: "16:00",
      physical_location: "الرياض",
    },
  );
  await page.locator(".workflow-steps button").nth(1).click();
  const form = page.locator(".property-form");
  await form.locator('[name="property.property_type"]').fill("عمارة");
  await form.locator('[name="property.city"]').fill("الرياض");
  // One deed to begin with, under its plain name.
  const first = form.locator('[name="property.deed_number"]');
  await first.fill("947603471790");
  const more = form.locator('[name="property.extra_deed_numbers"]');
  await expect(more).toHaveCount(0);
  await expect(form.getByLabel("Deed number", { exact: true })).toHaveCount(1);
  const add = form.getByRole("button", { name: "Add another deed" });
  const numbers = [
    "310115041563",
    "430107012766",
    "520118033311",
    "610115041564",
    "710115041565",
    "810115041566",
    "910115041567",
  ];
  for (const number of numbers) {
    await add.click();
    await more.last().fill(number);
  }
  // Eight at most, each named in the form.
  await expect(more).toHaveCount(7);
  await expect(add).toHaveCount(0);
  for (const n of [1, 2, 3, 4, 5, 6, 7, 8])
    await expect(
      form.getByLabel(`Deed number ${n}`, { exact: true }),
    ).toHaveCount(1);
  // The booklet page lists them as they are typed: under one label, two to a
  // line ("first - second").
  const preview = page.frameLocator(
    '.live-preview-paper iframe[aria-hidden="false"]',
  );
  await expect(
    // (Each number is kept left to right inside the Arabic line.)
    preview.getByText(/947603471790\W*-\W*310115041563/),
  ).toBeVisible();
  await expect(preview.getByText("910115041567")).toBeVisible();
  await expect(preview.getByText("رقم الصك الرابع")).toHaveCount(0);
  // Deeds can be taken away again; the rest keep their order.
  for (const n of [8, 7, 6, 5, 3])
    await form.getByRole("button", { name: `Remove deed ${n}` }).click();
  await expect(more).toHaveCount(2);
  await expect(add).toBeVisible();
  await expect(preview.getByText("910115041567")).toHaveCount(0);
  await form
    .getByRole("button", { name: "Save and close", exact: true })
    .click();
  await expect(page.locator(".property-cards li")).toHaveCount(1);
  const detail = await page.request
    .get("/api/projects/" + project.id)
    .then((r) => r.json());
  expect(detail.items[0].property_data.deed_number).toBe("947603471790");
  expect(detail.items[0].property_data.extra_deed_numbers).toEqual([
    "310115041563",
    "520118033311",
  ]);
  // Reopened, the stored deeds are there to edit.
  await page.locator(".property-cards li .property-card").click();
  await expect(more).toHaveCount(2);
  await expect(more.nth(1)).toHaveValue("520118033311");
  expect(errors).toEqual([]);
});
