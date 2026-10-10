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
test("a property takes up to four named deeds, shown on its booklet page", async ({
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
  for (const number of ["310115041563", "430107012766", "520118033311"]) {
    await add.click();
    await more.last().fill(number);
  }
  // Four at most, each named.
  await expect(more).toHaveCount(3);
  await expect(add).toHaveCount(0);
  for (const n of [1, 2, 3, 4])
    await expect(
      form.getByLabel(`Deed number ${n}`, { exact: true }),
    ).toHaveCount(1);
  // The booklet page names and lists them as they are typed.
  const preview = page.frameLocator(
    '.live-preview-paper iframe[aria-hidden="false"]',
  );
  await expect(preview.getByText("رقم الصك الرابع")).toBeVisible();
  await expect(preview.getByText("520118033311")).toBeVisible();
  // One can be taken away again; the rest keep their order.
  await form.getByRole("button", { name: "Remove deed 3" }).click();
  await expect(more).toHaveCount(2);
  await expect(add).toBeVisible();
  await expect(preview.getByText("رقم الصك الرابع")).toHaveCount(0);
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
