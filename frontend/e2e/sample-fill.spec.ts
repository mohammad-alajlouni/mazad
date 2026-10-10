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
test("sample fill completes a project that generates all its outputs", async ({
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
  const before: { id: string }[] = await page.request
    .get("/api/projects")
    .then((r) => r.json());
  // "Create project" opens the wizard directly: there is no form before it.
  await page
    .getByRole("button", { name: "Create project", exact: true })
    .first()
    .click();
  await expect(page.locator(".sample-fill")).toBeVisible();
  await page.getByRole("button", { name: "Sample fill" }).click();
  await page.getByRole("dialog").getByRole("button").last().click();
  // Three properties with their photographs, and every data step complete.
  await expect(
    page.getByText("3 properties and 4 images in this shared project"),
  ).toBeVisible({ timeout: 30000 });
  const steps = page.locator(".workflow-steps button");
  await expect(steps).toHaveCount(4);
  await expect(page.locator(".workflow-steps .step-missing")).toHaveCount(0);
  // The open form shows the filled values, not the ones it started with.
  await expect(page.locator('[name="auction_name"]')).not.toHaveValue("");
  await steps.nth(1).click();
  await expect(page.locator(".property-cards li")).toHaveCount(3);
  // Generating is the last step of the same wizard.
  await steps.nth(3).click();
  const generate = page
    .locator(".project-generation")
    .getByRole("button", { name: /Generate/ });
  await expect(generate).toBeEnabled({ timeout: 20000 });
  await generate.click();
  await expect(page.getByRole("status")).toContainText(/generated|ready/i, {
    timeout: 120000,
  });
  const p = (
    await page.request.get("/api/projects").then((r) => r.json())
  ).find((x: { id: string }) => !before.some((b) => b.id === x.id));
  // The project is called after its auction.
  expect(p.name).toBe(
    await page.request
      .get("/api/projects/" + p.id)
      .then((r) => r.json())
      .then((d) => d.project.auction.auction_name),
  );
  const detail = await page.request
    .get("/api/projects/" + p.id)
    .then((r) => r.json());
  expect(detail.outputs).toHaveLength(3);
  expect(errors).toEqual([]);
});
