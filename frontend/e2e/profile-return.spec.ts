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
test("the agent page sends to the profile and back without losing progress", async ({
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
  const project = await newProject(page, "Return " + Date.now());
  const form = page.locator(".auction-workspace form");
  // Unsaved values on the first page, then on to the agent's page.
  await page.locator('[name="auction_name"]').fill("UNSAVED NAME");
  await page.locator('[name="auction_date"]').fill("2026-10-10");
  const parts = page.locator(".page-parts");
  await parts.getByRole("button", { name: /Selling agent/ }).click();
  // The agent's details are not repeated here: a note and the way to them.
  const note = page.locator(".agent-note");
  await expect(note).toBeVisible();
  await expect(page.locator(".agent-card:not(.compact)")).toHaveCount(0);
  await expect(form).toContainText("in your profile");
  await expect(form).not.toContainText("0555000000");
  await note.getByRole("button", { name: "Go to my profile" }).click();
  const profile = page.locator(".account-profile");
  await expect(profile).toBeVisible();
  await expect(form).toBeHidden();
  const back = page.getByRole("button", { name: "Back to the booklet" });
  await expect(back).toBeVisible();
  // A change made in its own place reaches the project.
  await profile.locator('[name="phone"]').fill("0555999888");
  const saved = page.waitForResponse(
    (r) =>
      r.url().endsWith("/account/profile") && r.request().method() === "PUT",
  );
  await profile.getByRole("button", { name: "Save my details" }).click();
  expect((await saved).ok()).toBeTruthy();
  await back.click();
  // Back on the same page of the same step, with the unsaved values intact.
  await expect(profile).toHaveCount(0);
  await expect(note).toBeVisible();
  await expect(parts.locator(".selected")).toContainText("Selling agent");
  await expect(
    page
      .frameLocator('.live-preview-paper iframe[aria-hidden="false"]')
      .getByText("0555999888"),
  ).toBeVisible();
  await parts.getByRole("button", { name: /Cover/ }).click();
  await expect(page.locator('[name="auction_name"]')).toHaveValue(
    "UNSAVED NAME",
  );
  await expect(page.locator('[name="auction_date"]')).toHaveValue("2026-10-10");
  // Nothing was saved behind the author's back.
  const detail = await page.request
    .get("/api/projects/" + project.id)
    .then((r) => r.json());
  expect(detail.project.auction.auction_name).toBe(project.name);
  expect(detail.selling_agent.phone).toBe("0555999888");
  // From the sidebar too: the project is kept, and other pages leave it.
  await page
    .locator(".sidebar")
    .getByRole("button", { name: "My account settings", exact: true })
    .click();
  await expect(back).toBeVisible();
  await page
    .locator(".sidebar")
    .getByRole("button", { name: /My projects/ })
    .click();
  await expect(back).toHaveCount(0);
  await expect(profile).toHaveCount(0);
  expect(errors).toEqual([]);
});
