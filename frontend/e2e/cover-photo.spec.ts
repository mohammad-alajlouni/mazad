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
test("photographic covers take the author's photograph, the others do not", async ({
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
  const project = await newProject(page, "Cover photo " + Date.now());
  const form = page.locator(".auction-workspace form");
  const box = page.locator(".cover-photo-box");
  const choose = (cover: string) =>
    form.locator(`[name="cover-choice"][value="${cover}"]`).check({
      force: true,
    });
  // A cover without a photograph offers nothing to upload.
  await expect(box).toHaveCount(0);
  for (const cover of ["infath-1", "infath-6"]) {
    await choose(cover);
    await expect(box).toBeVisible();
  }
  await expect(box.locator("img")).toHaveCount(0);
  // Unsaved input on the page survives storing the photograph.
  await page.locator('[name="auction_date"]').fill("2026-10-10");
  const stored = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/projects/${project.id}/images`) &&
      r.request().method() === "POST",
  );
  await box
    .locator('input[type="file"]')
    .setInputFiles(path.join(root, "samples/demo-generator.jpg"));
  // The photograph is placed in the cover's own window before it is stored.
  const editor = page.locator("dialog.image-editor");
  await expect(editor).toBeVisible();
  const stage = await editor.locator(".editor-stage").boundingBox();
  expect(stage!.width / stage!.height).toBeCloseTo(595.28 / 590, 1);
  await usePhoto(page);
  const image = await (await stored).json();
  await expect(box.locator("img")).toBeVisible();
  await expect(page.locator('[name="auction_date"]')).toHaveValue("2026-10-10");
  await expect(
    form.locator('[name="cover-choice"][value="infath-6"]'),
  ).toBeChecked();
  // The live preview shows it under the cover's own frame.
  const preview = page.frameLocator(
    '.live-preview-paper iframe[aria-hidden="false"]',
  );
  await expect(preview.locator("img.cover-photo")).toHaveAttribute(
    "src",
    new RegExp(`/api/images/${image.id}`),
  );
  await expect(preview.locator("img.full-image")).toHaveAttribute(
    "src",
    /cover-6-frame\.png/,
  );
  await page.screenshot({
    path: path.join(root, "output/cover-photo.png"),
    fullPage: true,
  });
  // The other photographic cover shows the same photograph in its own design.
  await choose("infath-1");
  await expect(preview.locator("img.full-image")).toHaveAttribute(
    "src",
    /cover-1-frame\.png/,
  );
  // A cover without a photograph keeps its design and hides the control.
  await choose("infath-3");
  await expect(box).toHaveCount(0);
  await expect(preview.locator("img.cover-photo")).toHaveCount(0);
  // Going back to the built-in photograph removes the author's.
  await choose("infath-6");
  await box
    .getByRole("button", { name: "Use the built-in photograph" })
    .click();
  await expect(box.locator("img")).toHaveCount(0);
  await expect(preview.locator("img.cover-photo")).toHaveCount(0);
  await expect(preview.locator("img.full-image")).toHaveAttribute(
    "src",
    /reference-cover-6\.png/,
  );
  const detail = await page.request
    .get("/api/projects/" + project.id)
    .then((r) => r.json());
  expect(
    detail.images.filter((i: { category: string }) => i.category === "cover"),
  ).toHaveLength(0);
  expect(errors).toEqual([]);
});
