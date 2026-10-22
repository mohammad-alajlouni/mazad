import { completeAccount } from "./account-setup";
import { newProject } from "./required-setup";
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
// Nothing is wider than the phone's screen, and every one of the given
// controls lies wholly on it (not cut off at an edge).
async function fits(page: Page, controls: string) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  const width = page.viewportSize()!.width;
  for (const control of await page.locator(controls).all()) {
    if (!(await control.isVisible())) continue;
    const box = (await control.boundingBox())!;
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(width + 0.5);
  }
}
test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });
for (const locale of ["ar", "en"] as const)
  test(`the workspace fits a phone (${locale})`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/#login");
    await page.locator(".language-switcher").selectOption("en");
    await page.getByLabel("Email address").fill(env.ADMIN_EMAIL);
    await page.getByLabel("Password", { exact: true }).fill(env.ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Sign in to workspace" }).click();
    await completeAccount(page);
    const project = await newProject(
      page,
      `Phone ${locale} ${Date.now()}`,
      "project",
      {},
      {
        // A name the guide's boards and posts hold beside «مـزاد».
        auction_name: "مزاد الريان",
        auction_date: "2026-10-10",
        start_time: "16:00",
        physical_location: "الرياض",
        legal_announcement_text: "إعلان تجريبي",
      },
    );
    await page.locator(".language-switcher").selectOption(locale);
    await expect(page.locator("html")).toHaveAttribute("lang", locale);
    // The project's sections and the wizard's steps wrap onto rows.
    const tabs = ".project-sections button, .workflow-steps button";
    await expect(page.locator(".project-sections button")).toHaveCount(5);
    await fits(page, tabs + ", .page-parts button, .cover-option");
    // The live preview is out of the way until asked for, then fills the screen.
    const sheet = page.locator(".live-booklet-preview");
    const open = page.locator(".preview-open");
    await expect(sheet).not.toHaveClass(/open/);
    await expect(sheet).toHaveCSS("opacity", "0");
    await open.click();
    await expect(sheet).toHaveClass(/open/);
    const paper = (await page.locator(".live-preview-paper").boundingBox())!;
    expect(paper.width).toBeGreaterThan(330);
    await expect(
      page
        .frameLocator('.live-preview-paper iframe[aria-hidden="false"]')
        .locator("section")
        .first(),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(sheet).not.toHaveClass(/open/);
    // A property in the list shows its whole name, with its tools beneath.
    await page.request.post(`/api/projects/${project.id}/items`, {
      data: {
        title: "أرض تجارية على شارعين في حي النرجس شمال الرياض",
        property_data: { property_type: "أرض تجارية", city: "الرياض" },
      },
    });
    await page.reload();
    await page.locator(".sidebar nav button").first().waitFor({
      state: "attached",
    });
    await page.locator(".mobile-menu").click();
    await page.locator(".sidebar nav button").nth(1).click();
    // The project list is a list of cards, not a table cut at the edge.
    const row = page.locator("table.stacks tbody tr").first();
    await expect(row).toBeVisible();
    await fits(page, "table.stacks tbody tr, table.stacks td");
    await page.getByText(project.name, { exact: true }).first().click();
    await page.locator(".workflow-steps button").nth(1).click();
    const card = page.locator(".property-cards li").first();
    await expect(card).toContainText("شمال الرياض");
    await fits(
      page,
      tabs +
        ", .property-cards li, .property-tools button, .method-cards button",
    );
    await card.locator(".property-card").click();
    await expect(page.locator(".property-form")).toBeVisible();
    await fits(
      page,
      ".property-form input, .property-form textarea, .property-form .item-actions button, .property-photos .image-slot",
    );
    // The other sections of the project fit as well.
    for (const index of [1, 2, 3, 4]) {
      await page.locator(".project-sections button").nth(index).click();
      await fits(page, tabs + ", .panel");
    }
    await page.screenshot({
      path: path.join(root, `output/mobile-${locale}.png`),
      fullPage: true,
    });
    expect(errors).toEqual([]);
  });
