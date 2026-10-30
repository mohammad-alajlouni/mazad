import { completeAccount } from "./account-setup";
import { test, expect, type Page } from "@playwright/test";
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

// The agent's logo on the page shown: the widest logo image, in points.
async function logoWidth(page: Page, selector: string) {
  const frame = page.frameLocator(
    '.live-preview-paper iframe[aria-hidden="false"]',
  );
  return frame
    .locator(selector)
    .first()
    .evaluate((img: HTMLElement) => parseFloat(img.style.width));
}

test("the agent's logo is made larger or smaller from each live preview", async ({
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
  await page
    .getByRole("button", { name: "Create project", exact: true })
    .first()
    .click();
  await page.getByRole("button", { name: "Sample fill" }).click();
  await page.getByRole("dialog").getByRole("button").last().click();
  await expect(
    page.getByText(/properties and \d+ images in this shared project/),
  ).toBeVisible({ timeout: 30000 });

  // The booklet: what is typed in the form stays while the logo changes.
  await page.waitForLoadState("networkidle"); // the sample fill has settled
  const name = page.locator('input[name="auction_name"]');
  await name.fill("مزاد لم يحفظ بعد");
  const control = page.locator(".agent-logo-size");
  const shown = control.locator(".agent-logo-size-value");
  await expect(shown).toHaveText("100%");
  const paper = page.locator(".live-preview-paper");
  await expect(paper).toHaveAttribute("aria-busy", "false", { timeout: 20000 });
  const logo = "img.logo:not(.supervisor-logo)";
  const full = await logoWidth(page, logo);
  await page.getByRole("button", { name: "Make the logo smaller" }).click();
  await expect(shown).toHaveText("90%");
  await page.getByRole("button", { name: "Make the logo smaller" }).click();
  await expect(shown).toHaveText("80%");
  await expect
    .poll(() => logoWidth(page, logo), { timeout: 15000 })
    .toBeLessThan(full);
  await expect(name).toHaveValue("مزاد لم يحفظ بعد");
  await page.getByRole("button", { name: "Back to the original size" }).click();
  await expect(shown).toHaveText("100%");
  await expect
    .poll(() => logoWidth(page, logo), { timeout: 15000 })
    .toBeCloseTo(full, 0);
  await page.getByRole("button", { name: "Make the logo smaller" }).click();
  await expect(shown).toHaveText("90%");
  // The boards have a size of their own.
  // (A form with unsaved changes holds its section: it is saved first.)
  await page.locator("button.nav-next").click();
  await expect(page.getByRole("status")).toBeVisible();
  const sections = page.getByRole("navigation", { name: "Project sections" });
  await sections.getByRole("button", { name: "Banners", exact: true }).click();
  await expect(shown).toHaveText("100%");
  await expect(paper).toHaveAttribute("aria-busy", "false", { timeout: 20000 });
  const board = 'img.layer[alt=""]';
  const before = await logoWidth(page, board);
  await page.getByRole("button", { name: "Make the logo smaller" }).click();
  await expect(shown).toHaveText("90%");
  await expect
    .poll(() => logoWidth(page, board), { timeout: 15000 })
    .toBeLessThan(before);
  // Each kept its own, saved.
  await sections
    .getByRole("button", { name: "Project data", exact: true })
    .click();
  await expect(shown).toHaveText("90%");

  await page.locator(".language-switcher").selectOption("ar");
  await expect(page.locator(".agent-logo-size-title")).toHaveText(
    "حجم شعار الوكيل",
  );
  await page.locator(".live-booklet-preview").screenshot({
    path: path.join(root, "output/agent-logo-size.png"),
  });
  expect(errors).toEqual([]);
});
