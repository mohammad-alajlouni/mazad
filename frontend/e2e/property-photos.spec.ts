import { completeAccount } from "./account-setup";
import { newProject, usePhoto } from "./required-setup";
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
const photo = path.join(root, "samples/demo-generator.jpg");
test("a property's photographs are entered and changed in its own form", async ({
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
    "Photos " + Date.now(),
    "project",
    {},
    {
      auction_date: "2026-10-10",
      start_time: "16:00",
      physical_location: "الرياض",
      legal_announcement_text: "إعلان تجريبي",
    },
  );
  // No step of its own for photographs: they belong to each property.
  const steps = page.locator(".workflow-steps button");
  await expect(steps).toHaveCount(4);
  await steps.nth(1).click();
  await expect(page.locator(".workflow-steps")).not.toContainText("Images");
  const form = page.locator(".property-form");
  const slot = (role: string) => form.locator(`[data-slot="${role}"]`);
  const images = async () =>
    (
      await page.request
        .get("/api/projects/" + project.id)
        .then((r) => r.json())
    ).images.filter((i: { item_id: string | null }) => i.item_id) as {
      id: string;
      category: string;
    }[];
  // A new property: its details and its photographs together.
  await expect(form).toBeVisible();
  for (const [field, value] of Object.entries({
    property_type: "فيلا",
    city: "الرياض",
    district: "النرجس",
    plan_number: "3321",
    deed_number: "111",
    plot_number: "1",
    area: "600",
    usage: "سكني",
    execution_request_number: "12345",
  }))
    await form.locator(`[name="property.${field}"]`).fill(value);
  // Like its required details, the property is saved with its photograph.
  const mainInput = slot("main").locator('input[type="file"]');
  await form
    .getByRole("button", { name: "Save and close", exact: true })
    .click();
  expect(
    await mainInput.evaluate((e: HTMLInputElement) => e.validationMessage),
  ).toBe("Add the property's main photograph before saving.");
  await expect(page.locator(".property-cards li")).toHaveCount(0);
  await expect(slot("main")).toContainText("Required");
  await slot("main").locator('input[type="file"]').setInputFiles(photo);
  await usePhoto(page);
  await expect(slot("main")).toContainText("Saved with the property");
  await expect(slot("main").locator("img")).toBeVisible();
  // The picked photograph is already on this property's page in the preview.
  const preview = page.frameLocator(
    '.live-preview-paper iframe[aria-hidden="false"]',
  );
  await expect(preview.locator('image[href^="data:image/"]')).toHaveCount(1);
  await slot("additional")
    .locator('input[type="file"]')
    .setInputFiles([photo, photo]);
  await usePhoto(page, 2);
  await form
    .getByRole("button", { name: "Save and close", exact: true })
    .click();
  const card = page.locator(".property-cards li").first();
  await expect(card.locator("img.property-thumb")).toBeVisible();
  await expect(card).toContainText("Complete");
  let stored = await images();
  expect(stored.map((i) => i.category).sort()).toEqual([
    "additional",
    "additional",
    "main",
  ]);
  const firstMain = stored.find((i) => i.category === "main")!.id;
  // Reopened: drop one additional photograph, make the other the main one.
  await card.locator(".property-card").click();
  await expect(slot("main")).toContainText("Added");
  const thumbs = form.locator(".photo-thumbs li");
  await expect(thumbs).toHaveCount(2);
  await thumbs
    .nth(0)
    .getByRole("button", { name: "Remove photograph" })
    .click();
  await thumbs
    .nth(1)
    .getByRole("button", { name: "Make it the main photograph" })
    .click();
  await expect(form).toContainText("apply when the property is saved");
  // Nothing changes until the property is saved.
  expect(await images()).toHaveLength(3);
  await form.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByRole("status")).toBeVisible();
  await expect
    .poll(async () => (await images()).map((i) => i.category).sort())
    .toEqual(["additional", "main"]);
  stored = await images();
  const promoted = stored.find((i) => i.category === "main")!.id;
  expect(promoted).not.toBe(firstMain);
  // The earlier main photograph stays, as an additional one.
  expect(stored.find((i) => i.category === "additional")!.id).toBe(firstMain);
  // A new main photograph replaces the stored one instead of adding to it.
  await card.locator(".property-card").click();
  await slot("main").locator('input[type="file"]').setInputFiles(photo);
  await usePhoto(page);
  await form.getByRole("button", { name: "Save", exact: true }).click();
  await expect
    .poll(async () => {
      const now = await images();
      return (
        now.length === 2 &&
        now.every((i) => i.id !== promoted) &&
        now.some((i) => i.category === "main")
      );
    })
    .toBe(true);
  expect(errors).toEqual([]);
});
