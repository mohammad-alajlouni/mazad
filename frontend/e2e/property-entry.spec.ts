import { newProject } from "./required-setup";
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
test("properties are entered one after another without leaving the form", async ({
  page,
}) => {
  await page.goto("/");
  await page.locator(".language-switcher").selectOption("en");
  await page.getByLabel("Email address").fill(env.ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await completeAccount(page);
  const name = "Entry " + Date.now();
  await newProject(page, name, "booklet");
  const p = (
    await page.request.get("/api/projects").then((r) => r.json())
  ).find((x: { name: string }) => x.name === name);
  await page.request.put("/api/projects/" + p.id, {
    data: {
      ...p,
      auction: {
        ...p.auction,
        auction_date: "2026-10-10",
        start_time: "16:00",
        physical_location: "الرياض",
      },
    },
  });
  await page.reload();
  await page
    .locator(".sidebar")
    .getByRole("button", { name: /My projects/ })
    .click();
  await page.getByText(name, { exact: true }).click();
  await page.locator(".workflow-steps button").nth(1).click();

  // No property yet: the form is already open, numbered 01.
  const form = page.locator(".property-form");
  await expect(form.getByRole("heading")).toContainText("Property 01");
  for (const [field, value] of Object.entries({
    property_type: "أرض سكنية",
    city: "الرياض",
    district: "النرجس",
    plan_number: "3321",
    deed_number: "111",
    plot_number: "1",
    area: "600",
  }))
    await form.locator(`[name="property.${field}"]`).fill(value);
  await form
    .getByRole("button", { name: "Save and add a similar property" })
    .click();

  // The first is listed (named automatically) and a second form is open with
  // the shared values copied and the property's own numbers empty.
  const cards = page.locator(".property-cards li");
  await expect(cards).toHaveCount(1);
  await expect(cards.first()).toContainText("أرض سكنية · النرجس");
  await expect(form.getByRole("heading")).toContainText("Property 02");
  await expect(form.locator('[name="property.district"]')).toHaveValue(
    "النرجس",
  );
  await expect(form.locator('[name="property.plan_number"]')).toHaveValue(
    "3321",
  );
  await expect(form.locator('[name="property.deed_number"]')).toHaveValue("");
  await form.locator('[name="property.deed_number"]').fill("222");
  await form.locator('[name="property.plot_number"]').fill("2");
  await form.locator('[name="property.area"]').fill("650");
  await form
    .getByRole("button", { name: "Save and add a new property" })
    .click();
  await expect(cards).toHaveCount(2);
  await expect(form.getByRole("heading")).toContainText("Property 03");
  await expect(form.locator('[name="property.district"]')).toHaveValue("");
  // The save buttons stay in reach at the bottom of the screen.
  await expect(form.locator(".item-actions")).toBeInViewport();
});
