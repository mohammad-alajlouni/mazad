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
test("an output and a project are deleted from their lists, once confirmed", async ({
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
  const before: { id: string }[] = await page.request
    .get("/api/projects")
    .then((r) => r.json());
  // A complete project with its outputs (the booklet with its two forms,
  // the banners and the posts).
  await page
    .getByRole("button", { name: "Create project", exact: true })
    .first()
    .click();
  await page.getByRole("button", { name: "Sample fill" }).click();
  await page.getByRole("dialog").getByRole("button").last().click();
  await expect(
    page.getByText("3 properties and 4 images in this shared project"),
  ).toBeVisible({ timeout: 30000 });
  // A name of its own: sample names repeat, and the outputs list shows the
  // outputs of every project by its name.
  const created = (
    await page.request.get("/api/projects").then((r) => r.json())
  ).find((x: { id: string }) => !before.some((b) => b.id === x.id));
  const saved = await page.request
    .get("/api/projects/" + created.id)
    .then((r) => r.json());
  expect(
    (
      await page.request.put("/api/projects/" + created.id, {
        data: { ...saved.project, name: `حذف ${Date.now()}` },
      })
    ).status(),
  ).toBe(200);
  await page.locator(".workflow-steps button").nth(3).click();
  const generate = page
    .locator(".project-generation")
    .getByRole("button", { name: /Generate/ });
  await expect(generate).toBeEnabled({ timeout: 20000 });
  await generate.click();
  await expect(page.getByRole("status")).toContainText(/generated|ready/i, {
    timeout: 120000,
  });
  const p: { id: string; name: string; code: string } = (
    await page.request.get("/api/projects").then((r) => r.json())
  ).find((x: { id: string }) => !before.some((b) => b.id === x.id));
  const outputsOf = async () =>
    (await page.request.get("/api/outputs").then((r) => r.json())).filter(
      (o: { project_id: string }) => o.project_id === p.id,
    );
  // The booklet, the posts and the boards: one output for each board size
  // the properties take (Infath's table, by kind and area).
  const issued = (await outputsOf()).length;
  expect(issued).toBeGreaterThanOrEqual(3);

  // Outputs: each card has its own delete button, beside the card itself.
  const nav = page.locator(".sidebar nav");
  await nav.getByRole("button", { name: "Outputs", exact: true }).click();
  const cards = page.locator(".output-item").filter({ hasText: p.name });
  await expect(cards).toHaveCount(issued);
  const dialog = page.getByRole("dialog");
  const removeOutput = cards
    .first()
    .getByRole("button", { name: /^Delete output/ });
  await removeOutput.click();
  await expect(dialog).toContainText("can be generated again");
  // Cancelling leaves everything as it was.
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(cards).toHaveCount(issued);
  expect(await outputsOf()).toHaveLength(issued);
  await removeOutput.click();
  await dialog.getByRole("button", { name: "Confirm" }).click();
  await expect(page.locator(".toast.success")).toHaveText("Output deleted");
  await expect(cards).toHaveCount(issued - 1);
  expect(await outputsOf()).toHaveLength(issued - 1);
  // The card still opens its output.
  await cards.first().locator(".output-card").click();
  await expect(page.locator(".review")).toBeVisible();

  // Projects: the row opens the project, its delete button does not.
  await nav.locator("button").nth(1).click();
  const row = page.locator("table.project-table tbody tr").filter({
    hasText: p.code,
  });
  const removeProject = row.getByRole("button", { name: /^Delete project/ });
  await expect(removeProject).toBeVisible();
  // It stays within reach on a phone, without widening the page.
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(removeProject).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await removeProject.focus();
  await page.keyboard.press("Enter");
  await expect(dialog).toContainText(p.name);
  await expect(dialog).toContainText("cannot be undone");
  await expect(page.locator(".workflow-steps")).toHaveCount(0);
  await dialog.getByRole("button", { name: "Confirm" }).click();
  await expect(page.locator(".toast.success")).toHaveText("Project deleted");
  await expect(row).toHaveCount(0);
  expect((await page.request.get("/api/projects/" + p.id)).status()).toBe(404);
  expect(await outputsOf()).toHaveLength(0);
  expect(errors).toEqual([]);
});
