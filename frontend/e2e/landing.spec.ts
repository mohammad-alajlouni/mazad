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
test("visitors meet the landing page in both languages and enter the platform from it", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  const landing = page.locator(".lp");
  // Arabic first, right to left, with the real booklet pages in the hero.
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(landing.locator("h1")).toContainText("كل مطبوعات مزادك");
  await expect(landing.locator(".lp-sheet")).toHaveCount(4);
  const proof = landing.locator(".lp-proof");
  await expect(proof).toHaveAttribute("data-state", "spread");
  for (const image of await landing.locator(".lp-sheet").all())
    expect(
      await image.evaluate((e: HTMLImageElement) => e.naturalWidth),
    ).toBeGreaterThan(0);
  // "At the press of a button": the headline's button gathers the pages and
  // lays them out again.
  await landing.getByRole("button", { name: /^زر:/ }).click();
  await expect(proof).toHaveAttribute("data-state", "stacked");
  await expect(proof).toHaveAttribute("data-state", "spread");
  await expect(landing.locator(".lp-ticket")).toContainText("02");
  // The same page in English, left to right.
  await landing.locator(".language-switcher").selectOption("en");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(landing.locator("h1")).toContainText(
    "Every auction publication",
  );
  for (const title of [
    "The auction booklet",
    "Banners",
    "Social posts",
    "Four steps, in the order of the booklet's pages.",
  ])
    await expect(landing.getByRole("heading", { name: title })).toBeVisible();
  // It fits a phone in both languages.
  await page.setViewportSize({ width: 390, height: 844 });
  for (const locale of ["en", "ar"]) {
    await landing.locator(".language-switcher").selectOption(locale);
    await expect(page.locator("html")).toHaveAttribute("lang", locale);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
  }
  await page.screenshot({
    path: path.join(root, "output/landing-mobile.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await landing.locator(".language-switcher").selectOption("en");
  await page.screenshot({
    path: path.join(root, "output/landing-desktop.png"),
    fullPage: true,
  });
  // The button at the end of the page leads to the platform's sign-in.
  await landing
    .locator(".lp-final")
    .getByRole("button", { name: "Enter the platform" })
    .click();
  await expect(page).toHaveURL(/#login$/);
  await expect(page.getByLabel("Email address")).toBeVisible();
  await expect(landing).toHaveCount(0);
  // And back again, by the link or the browser's own Back.
  await page.getByRole("link", { name: "Back to the home page" }).click();
  await expect(landing.locator("h1")).toBeVisible();
  await landing.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByLabel("Email address")).toBeVisible();
  await page.goBack();
  await expect(landing.locator("h1")).toBeVisible();
  await page.goForward();
  // Signed in, the address shows the workspace, not the landing page.
  await page.getByLabel("Email address").fill(env.ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Sign in to workspace" }).click();
  await completeAccount(page);
  await expect(page.locator(".sidebar")).toBeAttached();
  await expect(page).not.toHaveURL(/#login$/);
  await page.goto("/");
  await expect(page.locator(".sidebar")).toBeAttached();
  await expect(landing).toHaveCount(0);
  // Logging out leaves the visitor at the sign-in form.
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByLabel("Email address")).toBeVisible();
  expect(errors).toEqual([]);
});
