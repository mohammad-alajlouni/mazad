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
const DAY = "rgb(245, 241, 232)";
const NIGHT = "rgb(7, 26, 40)";
// The device asks for a dark page: the site still opens by day.
test.use({ colorScheme: "dark" });
test("day is the default, and night is the visitor's choice everywhere", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const html = page.locator("html");
  const ground = (selector: string) =>
    page
      .locator(selector)
      .first()
      .evaluate((node) => getComputedStyle(node).backgroundColor);
  await page.goto("/");
  await page.locator(".language-switcher").selectOption("en");
  await expect(html).not.toHaveAttribute("data-theme", /.*/);
  expect(await ground(".lp")).toBe(DAY);
  const toggle = page.getByRole("button", {
    name: "Switch between day and night mode",
  });
  // Night, chosen on the landing page…
  await toggle.click();
  await expect(html).toHaveAttribute("data-theme", "dark");
  expect(await ground(".lp")).toBe(NIGHT);
  // …stays after a reload (the server renders it: nothing flashes)…
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", "dark");
  expect(await ground(".lp")).toBe(NIGHT);
  // …and on the sign-in page and in the workspace.
  await page.goto("/#login");
  await expect(page.locator(".login-form")).toBeVisible();
  expect(await ground("body")).toBe(NIGHT);
  await page.getByLabel("Email address").fill(env.ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await completeAccount(page);
  await expect(page.locator(".sidebar")).toBeAttached();
  expect(await ground(".main-content")).toBe(NIGHT);
  // A field is dark with light type, not a white box.
  const field = page.locator(".main-content input").first();
  if (await field.count())
    expect(
      await field.evaluate((node) => getComputedStyle(node).backgroundColor),
    ).not.toBe("rgb(255, 255, 255)");
  // Back to day from the workspace's own switch, and it is remembered.
  await page
    .locator(".topbar")
    .getByRole("button", { name: /day and night/ })
    .click();
  await expect(html).not.toHaveAttribute("data-theme", /.*/);
  expect(await ground(".main-content")).toBe(DAY);
  await page.reload();
  await expect(page.locator(".sidebar")).toBeAttached();
  await expect(html).not.toHaveAttribute("data-theme", /.*/);
  expect(await ground(".main-content")).toBe(DAY);
  expect(errors).toEqual([]);
});
