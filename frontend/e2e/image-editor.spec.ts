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
const photo = path.join(root, "samples/demo-generator.jpg");
test("every photograph is placed in its fixed frame before it is stored", async ({
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
    "Editor " + Date.now(),
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
  const editor = page.locator("dialog.image-editor");
  const stage = editor.locator(".editor-stage");
  const ratio = async () => {
    const box = (await stage.boundingBox())!;
    return box.width / box.height;
  };
  const main = form.locator('[data-slot="main"]');
  const pick = (slot = main) =>
    slot.locator('input[type="file"]').setInputFiles(photo);
  const stored = async () => {
    const detail = await page.request
      .get("/api/projects/" + project.id)
      .then((r) => r.json());
    return Promise.all(
      detail.images
        .filter((i: { item_id: string | null }) => i.item_id)
        .map(async (i: { id: string; category: string }) => {
          const data = await page.request
            .get(`/api/images/${i.id}`)
            .then((r) => r.body());
          const size = await page.evaluate(
            async (bytes) => {
              const bitmap = await createImageBitmap(
                new Blob([new Uint8Array(bytes)]),
              );
              return [bitmap.width, bitmap.height];
            },
            [...data],
          );
          return { category: i.category, ratio: size[0] / size[1] };
        }),
    );
  };

  // A type the booklet sets on a wide page: the frame is the wide one, fixed.
  await form.locator('[name="property.property_type"]').fill("أرض");
  await form.locator('[name="property.city"]').fill("الرياض");
  await pick();
  await expect(editor).toBeVisible();
  await expect(editor.locator(".frame-choice")).toHaveCount(0);
  expect(await ratio()).toBeCloseTo(500.2 / 292.7, 1);
  // Cancelling keeps nothing: no photograph is picked.
  await editor.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(editor).toBeHidden();
  await expect(main.locator("img")).toHaveCount(0);
  await expect(main).not.toContainText("demo-generator");

  // A type set on an upright page: the upright frame.
  await form.locator('[name="property.property_type"]').fill("عمارة");
  await pick();
  expect(await ratio()).toBeCloseTo(300.7 / 515, 1);
  await editor.getByRole("button", { name: "Cancel", exact: true }).click();

  // Neither: the author chooses the shape, starting from the photograph's own.
  await form.locator('[name="property.property_type"]').fill("مستودع");
  await pick();
  const choice = editor.locator(".frame-choice");
  await expect(choice.getByRole("button", { name: "Wide" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await choice.getByRole("button", { name: "Upright" }).click();
  expect(await ratio()).toBeCloseTo(300.7 / 515, 1);
  await choice.getByRole("button", { name: "Wide" }).click();
  expect(await ratio()).toBeCloseTo(500.2 / 292.7, 1);

  // The photograph can be made larger and moved, never out of its frame.
  const image = stage.locator("img");
  const before = (await image.boundingBox())!;
  await editor.getByRole("button", { name: "Larger" }).click();
  await editor.getByRole("button", { name: "Larger" }).click();
  const larger = (await image.boundingBox())!;
  expect(larger.width).toBeGreaterThan(before.width * 1.2);
  const frame = (await stage.boundingBox())!;
  await page.mouse.move(frame.x + frame.width / 2, frame.y + frame.height / 2);
  await page.mouse.down();
  await page.mouse.move(frame.x + frame.width + 900, frame.y + 900, {
    steps: 4,
  });
  await page.mouse.up();
  const moved = (await image.boundingBox())!;
  expect(moved.x).toBeGreaterThan(larger.x);
  // Dragged far past the edge, it stops where it still fills the frame.
  expect(moved.x).toBeLessThanOrEqual(frame.x + 1);
  expect(moved.y).toBeLessThanOrEqual(frame.y + 1);
  // Smaller than the frame is allowed too: it is centred on white.
  for (let n = 0; n < 8; n++)
    await editor.getByRole("button", { name: "Smaller" }).click();
  const whole = (await image.boundingBox())!;
  expect(whole.height).toBeLessThanOrEqual(frame.height + 1);
  expect(whole.width).toBeLessThanOrEqual(frame.width + 1);
  await editor.getByRole("button", { name: "Reset" }).click();
  await editor.getByRole("button", { name: "Use photograph" }).click();
  await expect(editor).toBeHidden();
  await expect(main.locator("img")).toBeVisible();

  // Additional photographs: one after another, in the images page's frame.
  await form
    .locator('[data-slot="additional"] input[type="file"]')
    .setInputFiles([photo, photo]);
  await expect(editor).toContainText("1 of 2");
  expect(await ratio()).toBeCloseTo(499.3 / 181.8, 1);
  await editor.getByRole("button", { name: "Use photograph" }).click();
  await expect(editor).toContainText("2 of 2");
  await editor.getByRole("button", { name: "Use photograph" }).click();
  await expect(editor).toBeHidden();
  await form
    .getByRole("button", { name: "Save and close", exact: true })
    .click();
  await expect(page.locator(".property-cards li")).toHaveCount(1);

  // What was stored is the frame's cut, not the 4:3 photograph that was picked.
  const cuts = await stored();
  expect(cuts).toHaveLength(3);
  for (const cut of cuts)
    expect(cut.ratio).toBeCloseTo(
      cut.category === "main" ? 500.2 / 292.7 : 499.3 / 181.8,
      1,
    );
  expect(errors).toEqual([]);
});
